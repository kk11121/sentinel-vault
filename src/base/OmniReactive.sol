// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { ISystemContract } from "../interfaces/ISystemContract.sol";
import { IReactive } from "../interfaces/IReactive.sol";

/// @title Minimal Omni reactive base, reimplemented from the documented API.
/// @notice The public reactive-lib on GitHub is still the legacy (RVM) version,
///         so the Omni surface described at dev.reactive.network is implemented
///         here directly: SYSTEM handle, onlySystem guard, payer behaviour.
abstract contract OmniReactive is IReactive {
    ISystemContract internal constant SYSTEM = ISystemContract(payable(0x8888888888888888888888888888888888888888));
    uint256 internal constant REACTIVE_IGNORE = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF;

    error NotAuthorized();

    modifier onlySystem() {
        if (msg.sender != address(SYSTEM)) revert NotAuthorized();
        _;
    }

    /// @notice Called by the system contract to collect payment for execution.
    function pay(uint256 amount_) external onlySystem {
        (bool ok,) = payable(address(SYSTEM)).call{ value: amount_ }("");
        require(ok, "pay failed");
    }

    function _coverDebt() internal {
        uint256 debt = SYSTEM.debts(address(this));
        if (debt > 0) {
            (bool ok,) = payable(address(SYSTEM)).call{ value: debt }("");
            require(ok, "coverDebt failed");
        }
    }

    receive() external payable virtual { }
}
