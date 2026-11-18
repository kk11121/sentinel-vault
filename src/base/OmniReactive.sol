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
    // Wildcard sentinel as actually used by working on-chain subscriptions.
    // NOTE: the docs table calls the wildcard "REACTIVE_IGNORE" without giving
    // its value; 0xFFFF...FF is recorded by the system contract but never
    // matches in validator delivery (verified empirically 2026-11-17 by
    // byte-comparing live subscription events). The value below is the one
    // every delivered subscription on Lasna uses.
    uint256 internal constant REACTIVE_IGNORE = 0xa65f96fc951c35ead38878e0f0b7a3c744a6f5ccc1476b313353ce31712313ad;

    error NotAuthorized();

    modifier onlySystem() {
        if (msg.sender != address(SYSTEM)) revert NotAuthorized();
        _;
    }

    /// @notice Called by the system contract to collect payment for execution.
    /// @dev The amount is named by the system contract under the Reactive
    ///      fee model; there is deliberately no cap here — a cap below the
    ///      real fee would break reactive delivery. This is a documented
    ///      platform trust assumption (see README), bounded in practice by
    ///      this contract's balance and the reserves accounting.
    function pay(uint256 amount_) external onlySystem {
        (bool ok,) = payable(address(SYSTEM)).call{ value: amount_ }("");
        require(ok, "pay failed");
    }

    receive() external payable virtual { }
}
