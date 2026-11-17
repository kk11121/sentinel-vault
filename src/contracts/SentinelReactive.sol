// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniReactive } from "../base/OmniReactive.sol";
import { ISystemContract } from "../interfaces/ISystemContract.sol";
import { LogRecord } from "../interfaces/IReactive.sol";

/// @title SentinelReactive — the Lasna RSC that turns verdicts into action.
/// @notice The RSC does two jobs no single-chain component can do:
///           1. Enforcement relay with least privilege: it watches the
///              VerdictRegistry on Base Sepolia and turns verdicts into
///              veto/freeze callbacks on three chains, so the AI's key
///              only ever writes on one chain and holds no freeze power.
///           2. Cross-chain pace guard: it also watches WithdrawalRequested
///              on every vault. A single vault cannot see the aggregate
///              pace across chains; if requests across ALL vaults exceed
///              PACE_LIMIT within PACE_WINDOW, the RSC freezes everything
///              on its own — no AI verdict needed.
///         Verdict policy (A' design):
///           LOW    -> nothing (the withdrawal executes fail-open).
///           MEDIUM -> veto that one withdrawal on its origin vault.
///           HIGH   -> veto + freeze every configured vault.
///           A second MEDIUM for the same vault within ESCALATION_WINDOW
///           escalates to HIGH (preemptive freeze, reason ESCALATED).
///         A MEDIUM verdict naming a request this RSC has never seen is
///         ignored (it cannot veto what does not exist); a HIGH verdict
///         freezes regardless, but is flagged UnverifiedVerdict — a freeze
///         is recoverable, a missed one may not be.
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
    // vault => timestamp of the latest MEDIUM verdict against it
    mapping(address => uint256) public lastMediumAt;
    // keccak256(abi.encode(chainId, vault, requestId)) => request observed
    mapping(bytes32 => bool) public knownRequests;

    uint256 public paceWindowStart;
    uint256 public paceCount;
    bool public paceFrozen;

    uint256 internal verdictTopic0;
    uint256 internal withdrawalTopic0;

    event VaultSet(uint256 indexed chainId, address vault);
    event RequestSeen(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event VerdictIgnored(uint256 indexed requestId, uint8 severity);
    event UnverifiedVerdict(uint256 indexed chainId, address indexed vault, uint256 indexed requestId, uint8 severity);
    event VetoRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event FreezeRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event Escalated(address indexed vault, uint256 indexed requestId);
    event PaceFreeze(uint256 count, uint256 windowStart);

    error NotOwner();

    constructor(address registry_) payable {
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
    function watchVault(uint256 chainId_, address vault_) external {
        if (msg.sender != owner) revert NotOwner();
        vaults[chainId_] = vault_;
        SYSTEM.subscribe(chainId_, vault_, withdrawalTopic0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
        emit VaultSet(chainId_, vault_);
    }

    function requestKey(uint256 chainId_, address vault_, uint256 requestId_) public pure returns (bytes32) {
        return keccak256(abi.encode(chainId_, vault_, requestId_));
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
        knownRequests[requestKey(log_.chainId, log_.contractAddress, requestId)] = true;
        emit RequestSeen(log_.chainId, log_.contractAddress, requestId);

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
        bool known = knownRequests[requestKey(chainId, vault, requestId)];

        if (severity == SEVERITY_HIGH) {
            if (!known) emit UnverifiedVerdict(chainId, vault, requestId, severity);
            _freezeAll(requestId, REASON_HIGH);
            return;
        }
        if (severity == SEVERITY_MEDIUM) {
            if (!known) {
                emit UnverifiedVerdict(chainId, vault, requestId, severity);
                emit VerdictIgnored(requestId, severity);
                return;
            }
            uint256 last = lastMediumAt[vault];
            lastMediumAt[vault] = block.timestamp;
            if (last != 0 && block.timestamp - last <= ESCALATION_WINDOW) {
                emit Escalated(vault, requestId);
                _freezeAll(requestId, REASON_ESCALATED);
                return;
            }
            (uint256 originChain, bool found) = _chainOf(vault);
            if (found) {
                bytes memory payload = abi.encodeWithSignature("veto(address,uint256)", address(0), requestId);
                _requestCallback(originChain, vault, payload);
                emit VetoRequested(originChain, vault, requestId);
            }
            return;
        }
        emit VerdictIgnored(requestId, severity);
    }

    function _chainOf(address vault_) internal view returns (uint256, bool) {
        uint256[3] memory chains = [uint256(84532), uint256(11155111), uint256(1301)];
        for (uint256 i = 0; i < chains.length; i++) {
            if (vaults[chains[i]] == vault_) return (chains[i], true);
        }
        return (0, false);
    }

    function _freezeAll(uint256 requestId_, bytes32 reason_) internal {
        uint256[3] memory chains = [uint256(84532), uint256(11155111), uint256(1301)];
        for (uint256 i = 0; i < chains.length; i++) {
            address vault = vaults[chains[i]];
            if (vault == address(0)) continue;
            bytes memory payload = abi.encodeWithSignature("freeze(address,bytes32)", address(0), reason_);
            _requestCallback(chains[i], vault, payload);
            emit FreezeRequested(chains[i], vault, requestId_);
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
