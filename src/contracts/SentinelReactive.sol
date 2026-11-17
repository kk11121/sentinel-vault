// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniReactive } from "../base/OmniReactive.sol";
import { ISystemContract } from "../interfaces/ISystemContract.sol";
import { LogRecord } from "../interfaces/IReactive.sol";

/// @title SentinelReactive — the Lasna RSC that turns verdicts into action.
/// @notice Policy (A' design):
///           LOW    -> nothing (the withdrawal executes fail-open).
///           MEDIUM -> veto that one withdrawal on its origin vault.
///           HIGH   -> veto + freeze every configured vault.
///           A second MEDIUM for the same vault within ESCALATION_WINDOW
///           escalates to HIGH (preemptive freeze, reason ESCALATED).
///         Deployment order per the docs: deploy this first, then the
///         vaults with this address as callback sender, then setVault().
contract SentinelReactive is OmniReactive {
    uint256 public constant REGISTRY_CHAIN_ID = 84532; // Base Sepolia
    uint64 public constant CALLBACK_GAS_LIMIT = 1_000_000;
    uint256 public constant ESCALATION_WINDOW = 1 hours;

    uint8 internal constant SEVERITY_MEDIUM = 1;
    uint8 internal constant SEVERITY_HIGH = 2;

    bytes32 internal constant REASON_HIGH = "HIGH_VERDICT";
    bytes32 internal constant REASON_ESCALATED = "ESCALATED";

    address public owner;
    address public registry;

    // destination chainId => vault address (0 = not configured)
    mapping(uint256 => address) public vaults;
    // vault => timestamp of the latest MEDIUM verdict against it
    mapping(address => uint256) public lastMediumAt;

    uint256 internal verdictTopic0;

    event VaultSet(uint256 indexed chainId, address vault);
    event VerdictIgnored(uint256 indexed requestId, uint8 severity);
    event VetoRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event FreezeRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);
    event Escalated(address indexed vault, uint256 indexed requestId);

    error NotOwner();

    constructor(address registry_) payable {
        owner = msg.sender;
        registry = registry_;
        verdictTopic0 = uint256(keccak256("VerdictPosted(uint256,address,uint8,uint256,bytes32,bytes32)"));
        SYSTEM.subscribe(
            REGISTRY_CHAIN_ID, registry_, verdictTopic0, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE
        );
    }

    function setVault(uint256 chainId_, address vault_) external {
        if (msg.sender != owner) revert NotOwner();
        vaults[chainId_] = vault_;
        emit VaultSet(chainId_, vault_);
    }

    /// @notice System-contract entry point for subscribed VerdictPosted logs.
    function react(LogRecord memory log_) external override onlySystem {
        if (log_.topic0 != verdictTopic0) return;
        uint256 requestId = log_.topic1;
        address vault = address(uint160(log_.topic2));
        (uint8 severity,,,) = abi.decode(log_.data, (uint8, uint256, bytes32, bytes32));

        if (severity == SEVERITY_HIGH) {
            _freezeAll(requestId, REASON_HIGH);
            return;
        }
        if (severity == SEVERITY_MEDIUM) {
            uint256 last = lastMediumAt[vault];
            lastMediumAt[vault] = block.timestamp;
            if (last != 0 && block.timestamp - last <= ESCALATION_WINDOW) {
                emit Escalated(vault, requestId);
                _freezeAll(requestId, REASON_ESCALATED);
                return;
            }
            (uint256 chainId, bool found) = _chainOf(vault);
            if (found) {
                bytes memory payload = abi.encodeWithSignature("veto(address,uint256)", address(0), requestId);
                _requestCallback(chainId, vault, payload);
                emit VetoRequested(chainId, vault, requestId);
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
