// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniReactive } from "../base/OmniReactive.sol";
import { ISystemContract } from "../interfaces/ISystemContract.sol";
import { LogRecord } from "../interfaces/IReactive.sol";

/// @title SentinelReactive — the Lasna RSC that turns verdicts into action.
/// @notice Subscribes to VerdictPosted on the registry (Base Sepolia).
///         M1 policy: HIGH -> freeze the configured vaults via callbacks.
///         MEDIUM (veto) and the MEDIUMx2 escalation arrive with the M2
///         vault queue. Deployment order per the docs: deploy this first,
///         then the vaults with this address as callback sender, then set
///         the vault recipients here via setVault().
contract SentinelReactive is OmniReactive {
    uint256 public constant REGISTRY_CHAIN_ID = 84532; // Base Sepolia
    uint64 public constant CALLBACK_GAS_LIMIT = 1_000_000;

    uint8 internal constant SEVERITY_MEDIUM = 1;
    uint8 internal constant SEVERITY_HIGH = 2;

    bytes32 internal constant REASON_HIGH = "HIGH_VERDICT";
    bytes32 internal constant REASON_ESCALATED = "ESCALATED";

    address public owner;
    address public registry;

    // destination chainId => vault address (0 = not configured)
    mapping(uint256 => address) public vaults;

    uint256 internal verdictTopic0;

    event VaultSet(uint256 indexed chainId, address vault);
    event VerdictIgnored(uint256 indexed requestId, uint8 severity);
    event FreezeRequested(uint256 indexed chainId, address indexed vault, uint256 indexed requestId);

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
        (uint8 severity,,,) = abi.decode(log_.data, (uint8, uint256, bytes32, bytes32));
        if (severity != SEVERITY_HIGH) {
            emit VerdictIgnored(requestId, severity);
            return;
        }
        _freezeAll(requestId, REASON_HIGH);
    }

    function _freezeAll(uint256 requestId_, bytes32 reason_) internal {
        uint256[3] memory chains = [uint256(84532), uint256(11155111), uint256(1301)];
        for (uint256 i = 0; i < chains.length; i++) {
            address vault = vaults[chains[i]];
            if (vault == address(0)) continue;
            bytes memory payload = abi.encodeWithSignature("freeze(address,bytes32)", address(0), reason_);
            SYSTEM.requestCallbackV_1_0(
                ISystemContract.CallbackConfiguration_V_1_0({
                    chainId: chains[i], recipient: vault, gasLimit: CALLBACK_GAS_LIMIT, payload: payload
                })
            );
            emit FreezeRequested(chains[i], vault, requestId_);
        }
    }
}
