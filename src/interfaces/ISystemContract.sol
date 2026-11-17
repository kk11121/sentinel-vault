// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title Minimal Omni system-contract interface (per https://dev.reactive.network/)
/// @notice Only the surface Sentinel Vault uses. The system contract lives at
///         0x8888888888888888888888888888888888888888 on Reactive Network.
interface ISystemContract {
    enum CallbackVersion {
        V_1_0
    }

    struct CallbackConfiguration_V_1_0 {
        uint256 chainId;
        address recipient;
        uint64 gasLimit;
        bytes payload;
    }

    function subscribe(
        uint256 chainId_,
        address contract_,
        uint256 topic0_,
        uint256 topic1_,
        uint256 topic2_,
        uint256 topic3_
    ) external;

    function unsubscribe(
        uint256 chainId_,
        address contract_,
        uint256 topic0_,
        uint256 topic1_,
        uint256 topic2_,
        uint256 topic3_
    ) external;

    function requestCallbackV_1_0(CallbackConfiguration_V_1_0 memory config_) external;

    function debts(address) external view returns (uint256);
}
