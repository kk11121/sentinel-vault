// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniCallback } from "../base/OmniCallback.sol";

/// @title GuardedVault — the vault the Sentinel watches.
/// @notice M1 scope: deposits, freeze/unfreeze. The withdrawal queue, veto
///         and fail-open execution arrive in M2. freeze() is reachable only
///         as a Reactive callback: the caller must be this chain's callback
///         proxy and the injected sender must be the Sentinel RSC.
contract GuardedVault is OmniCallback {
    address public owner;
    bool public frozen;

    event Deposited(address indexed from, uint256 amount);
    event Frozen(address indexed reactive, bytes32 reasonCode);
    event Unfrozen(address indexed by);

    error NotOwner();
    error AlreadyFrozen();

    constructor(address owner_, address callbackProxy_, address callbackSender_)
        payable
        OmniCallback(callbackProxy_, callbackSender_)
    {
        owner = owner_;
    }

    function deposit() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    /// @notice Freeze this vault. First argument is overwritten by the
    ///         callback proxy with the requesting reactive contract.
    function freeze(address reactive_, bytes32 reasonCode_)
        external
        onlyServiceProvider
        onlyCallbackSender(reactive_)
    {
        if (frozen) revert AlreadyFrozen();
        frozen = true;
        emit Frozen(reactive_, reasonCode_);
    }

    function unfreeze() external {
        if (msg.sender != owner) revert NotOwner();
        frozen = false;
        emit Unfrozen(msg.sender);
    }

    function coverDebt() external {
        // Callback-side debt is settled by the proxy through pay(); this
        // entry point exists so the owner can top up reserves via depositTo
        // flows documented in the Economy page. No-op by design in M1.
    }
}
