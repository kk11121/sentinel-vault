// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniReactive } from "../base/OmniReactive.sol";
import { ISystemContract } from "../interfaces/ISystemContract.sol";
import { LogRecord } from "../interfaces/IReactive.sol";

/// @title SentinelReactive — the Lasna RSC that turns verdicts into action.
/// @notice The RSC does two jobs no single-chain component can do:
///           1. Enforcement relay with least privilege: it watches the
///              VerdictRegistry on Base Sepolia and turns verdicts into
///              veto/freeze callbacks on every watched chain, so the AI's
///              key only ever writes on one chain and holds no freeze power.
///           2. Cross-chain pace guard: it also watches WithdrawalRequested
///              on every vault. A single vault cannot see the aggregate
///              pace across chains; if requests across ALL vaults exceed
///              PACE_LIMIT within PACE_WINDOW, the RSC freezes everything
///              on its own — no AI verdict needed.
///         Verdict policy (A' design):
///           LOW    -> nothing (the withdrawal executes fail-open).
///           MEDIUM -> veto that one withdrawal on its origin vault.
///           HIGH   -> veto that withdrawal AND freeze every watched vault.
///           A second MEDIUM for the same vault (on the same chain) within
///           ESCALATION_WINDOW escalates to HIGH (preemptive freeze,
///           reason ESCALATED) — and also vetoes its own withdrawal.
///         Delivery order between the origin chain and the registry chain
///         is NOT guaranteed, so a verdict that arrives before its
///         WithdrawalRequested is not dropped: it is recorded as a
///         pending veto and applied the moment the request is seen. A
///         HIGH verdict freezes immediately regardless (a freeze is
///         recoverable, a missed one may not be) and is flagged
///         UnverifiedVerdict when its request has not been seen yet.
///         Deployment order: deploy this first (it subscribes to the
///         registry in its constructor), then the vaults with this address
///         as callback sender, then watchVault() for each vault.
contract SentinelReactive is OmniReactive {
    uint256 public constant REGISTRY_CHAIN_ID = 84532; // Base Sepolia
    uint64 public constant CALLBACK_GAS_LIMIT = 1_000_000;
    uint256 public constant ESCALATION_WINDOW = 1 hours;
    uint256 public constant PACE_WINDOW = 1 hours;
    uint256 public constant PACE_LIMIT = 10;

    uint8 internal constant SEVERITY_MEDIUM = 1;
    uint8 internal constant SEVERITY_HIGH = 2;

    bytes32 internal constant REASON_HIGH = "HIGH_VERDICT";
    bytes32 internal constant REASON_ESCALATED = "ESCALATED";
    bytes32 internal constant REASON_PACE = "PACE_LIMIT";

    address public owner;
    address public registry;

    // destination chainId => vault address (0 = not configured)
    mapping(uint256 => address) public vaults;
    // vault address => its chainId (routing for callbacks)
    mapping(address => uint256) public vaultChain;
    // every chainId ever passed to watchVault, for _freezeAll
    uint256[] public watchedChains;
    mapping(uint256 => bool) internal chainListed;
    // keccak256(abi.encode(chainId, vault)) => latest MEDIUM timestamp.
    // Keyed per (chain, vault): the same vault address deployed on two
    // chains must never share escalation state.
    mapping(bytes32 => uint256) public lastMediumAt;
    // keccak256(abi.encode(chainId, vault, requestId)) => request observed
    mapping(bytes32 => bool) public knownRequests;
    // keccak256(abi.encode(chainId, vault, requestId)) => severity of a
    // verdict that arrived before its request (0 = none). Applied when
    // the request is seen.
    mapping(bytes32 => uint8) public pendingVetoes;

    uint256 public paceWindowStart;
    uint256 public paceCount;
    bool public paceFrozen;

    uint256 internal verdictTopic0;
    uint256 internal withdrawalTopic0;

    event VaultSet(uint256 indexed chainId, address vault);
    event RequestSeen(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event VerdictIgnored(uint256 indexed requestId, uint8 severity);
    event VerdictForUnwatched(uint256 indexed chainId, address indexed vault, uint256 indexed requestId, uint8 severity);
    event UnverifiedVerdict(uint256 indexed chainId, address indexed vault, uint256 indexed requestId, uint8 severity);
    event PendingVetoRecorded(uint256 indexed chainId, address indexed vault, uint256 indexed requestId, uint8 severity);
    event PendingVetoApplied(uint256 indexed chainId, address indexed vault, uint256 indexed requestId, uint8 severity);
    event VetoRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event FreezeRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event Escalated(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event PaceFreeze(uint256 count, uint256 windowStart);

    error NotOwner();
    error ZeroAddress();

    constructor(address registry_) payable {
        if (registry_ == address(0)) revert ZeroAddress();
        owner = msg.sender;
        registry = registry_;
        verdictTopic0 = uint256(keccak256("VerdictPosted(uint256,address,uint256,uint8,uint256,bytes32,bytes32)"));
        withdrawalTopic0 = uint256(keccak256("WithdrawalRequested(uint256,address,address,uint256,uint256)"));
        paceWindowStart = block.timestamp;
        SYSTEM.subscribe(
            REGISTRY_CHAIN_ID, registry_, verdictTopic0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE
        );
    }

    /// @notice Register a vault: remember it for callback routing AND
    ///         subscribe to its WithdrawalRequested events on its chain.
    ///         Idempotent for the same (chainId, vault) pair — a duplicate
    ///         registration must not create a duplicate subscription,
    ///         which would double-count the pace guard.
    function watchVault(uint256 chainId_, address vault_) external {
        if (msg.sender != owner) revert NotOwner();
        if (vault_ == address(0)) revert ZeroAddress();
        if (vaults[chainId_] == vault_) return;
        address previous = vaults[chainId_];
        if (previous != address(0) && vaultChain[previous] == chainId_) {
            delete vaultChain[previous];
        }
        vaults[chainId_] = vault_;
        vaultChain[vault_] = chainId_;
        if (!chainListed[chainId_]) {
            chainListed[chainId_] = true;
            watchedChains.push(chainId_);
        }
        SYSTEM.subscribe(chainId_, vault_, withdrawalTopic0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
        emit VaultSet(chainId_, vault_);
    }

    function watchedChainCount() external view returns (uint256) {
        return watchedChains.length;
    }

    function requestKey(uint256 chainId_, address vault_, uint256 requestId_) public pure returns (bytes32) {
        return keccak256(abi.encode(chainId_, vault_, requestId_));
    }

    function vaultKey(uint256 chainId_, address vault_) public pure returns (bytes32) {
        return keccak256(abi.encode(chainId_, vault_));
    }

    /// @notice System-contract entry point for subscribed logs.
    function react(LogRecord memory log_) external override onlySystem {
        if (log_.topic0 == verdictTopic0) {
            _reactVerdict(log_);
        } else if (log_.topic0 == withdrawalTopic0) {
            _reactWithdrawal(log_);
        }
    }

    function _reactWithdrawal(LogRecord memory log_) internal {
        // Only trust logs actually emitted by the watched vault on its chain.
        if (log_.contractAddress != vaults[log_.chainId]) return;
        uint256 requestId = log_.topic1;
        bytes32 key = requestKey(log_.chainId, log_.contractAddress, requestId);
        // Idempotent delivery: the same log delivered twice (subscription
        // overlap, reorg re-delivery) must not double-count the pace guard
        // or re-apply a pending veto.
        if (knownRequests[key]) return;
        knownRequests[key] = true;
        emit RequestSeen(log_.chainId, log_.contractAddress, requestId);

        // A verdict that beat its own request here is applied now.
        uint8 pending = pendingVetoes[key];
        if (pending != 0) {
            delete pendingVetoes[key];
            emit PendingVetoApplied(log_.chainId, log_.contractAddress, requestId, pending);
            if (pending == SEVERITY_HIGH) {
                _sendVeto(log_.chainId, log_.contractAddress, requestId);
            } else if (pending == SEVERITY_MEDIUM) {
                _applyMedium(log_.chainId, log_.contractAddress, requestId);
            }
        }

        if (block.timestamp >= paceWindowStart + PACE_WINDOW) {
            paceWindowStart = block.timestamp;
            paceCount = 0;
            paceFrozen = false;
        }
        paceCount++;
        if (paceCount > PACE_LIMIT && !paceFrozen) {
            paceFrozen = true;
            emit PaceFreeze(paceCount, paceWindowStart);
            _freezeAll(requestId, REASON_PACE);
        }
    }

    function _reactVerdict(LogRecord memory log_) internal {
        // The verdict must come from the registry contract on its own chain;
        // the subscription already filters this, and we check again so the
        // policy never acts on a log that merely looks like a verdict.
        if (log_.chainId != REGISTRY_CHAIN_ID || log_.contractAddress != registry) return;
        uint256 chainId = log_.topic1;
        address vault = address(uint160(log_.topic2));
        uint256 requestId = log_.topic3;
        (uint8 severity,,,) = abi.decode(log_.data, (uint8, uint256, bytes32, bytes32));
        // Only act on verdicts about a vault this RSC actually watches on
        // that chain. The registry is a public posting board for the
        // writer key; a verdict naming any other (chain, vault) pair — a
        // stale worker configuration, another deployment sharing the
        // registry, or a hand-posted entry — must not move callbacks,
        // record pending vetoes, or touch escalation state.
        if (vaults[chainId] != vault) {
            emit VerdictForUnwatched(chainId, vault, requestId, severity);
            return;
        }
        bytes32 key = requestKey(chainId, vault, requestId);
        bool known = knownRequests[key];

        if (severity == SEVERITY_HIGH) {
            if (!known) {
                emit UnverifiedVerdict(chainId, vault, requestId, severity);
                _recordPending(key, chainId, vault, requestId, SEVERITY_HIGH);
            } else {
                // The flagged withdrawal itself is vetoed, not just paused:
                // after a recovery unfreeze it must stay dead.
                _sendVeto(chainId, vault, requestId);
            }
            _freezeAll(requestId, REASON_HIGH);
            return;
        }
        if (severity == SEVERITY_MEDIUM) {
            if (!known) {
                emit UnverifiedVerdict(chainId, vault, requestId, severity);
                _recordPending(key, chainId, vault, requestId, SEVERITY_MEDIUM);
                return;
            }
            _applyMedium(chainId, vault, requestId);
            return;
        }
        emit VerdictIgnored(requestId, severity);
    }

    /// @notice MEDIUM policy for a request known to exist: record the
    ///         strike, escalate on a second strike within the window
    ///         (veto + freeze), otherwise veto just this withdrawal.
    function _applyMedium(uint256 chainId_, address vault_, uint256 requestId_) internal {
        bytes32 vKey = vaultKey(chainId_, vault_);
        uint256 last = lastMediumAt[vKey];
        lastMediumAt[vKey] = block.timestamp;
        if (last != 0 && block.timestamp - last <= ESCALATION_WINDOW) {
            emit Escalated(chainId_, vault_, requestId_);
            _sendVeto(chainId_, vault_, requestId_);
            _freezeAll(requestId_, REASON_ESCALATED);
            return;
        }
        _sendVeto(chainId_, vault_, requestId_);
    }

    function _recordPending(
        bytes32 key_,
        uint256 chainId_,
        address vault_,
        uint256 requestId_,
        uint8 severity_
    ) internal {
        // Keep the stronger severity if both arrive early.
        if (pendingVetoes[key_] < severity_) {
            pendingVetoes[key_] = severity_;
        }
        emit PendingVetoRecorded(chainId_, vault_, requestId_, severity_);
    }

    function _sendVeto(uint256 chainId_, address vault_, uint256 requestId_) internal {
        bytes memory payload = abi.encodeWithSignature("veto(address,uint256)", address(0), requestId_);
        _requestCallback(chainId_, vault_, payload);
        emit VetoRequested(chainId_, vault_, requestId_);
    }

    function _freezeAll(uint256 requestId_, bytes32 reason_) internal {
        for (uint256 i = 0; i < watchedChains.length; i++) {
            uint256 chainId = watchedChains[i];
            address vault = vaults[chainId];
            if (vault == address(0)) continue;
            bytes memory payload = abi.encodeWithSignature("freeze(address,bytes32)", address(0), reason_);
            _requestCallback(chainId, vault, payload);
            emit FreezeRequested(chainId, vault, requestId_);
        }
    }

    function _requestCallback(uint256 chainId_, address recipient_, bytes memory payload_) internal {
        SYSTEM.requestCallbackV_1_0(
            ISystemContract.CallbackConfiguration_V_1_0({
                chainId: chainId_, recipient: recipient_, gasLimit: CALLBACK_GAS_LIMIT, payload: payload_
            })
        );
    }
}
