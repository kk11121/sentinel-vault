// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title Minimal Omni callback base, reimplemented from the documented API.
/// @notice Authentication model per https://dev.reactive.network/callback-contracts:
///         the caller must be the chain's callback proxy (onlyServiceProvider),
///         and the first payload argument — overwritten by the proxy with the
///         requesting reactive contract's address — must match the authorized
///         reactive contract (onlyCallbackSender).
abstract contract OmniCallback {
    address internal immutable _CALLBACK_PROXY;
    address internal immutable _CALLBACK_SENDER;

    error NotAuthorized();
    error CallbackNotAuthorized();

    constructor(address callbackProxy_, address callbackSender_) payable {
        _CALLBACK_PROXY = callbackProxy_;
        _CALLBACK_SENDER = callbackSender_;
    }

    modifier onlyServiceProvider() {
        if (msg.sender != _CALLBACK_PROXY) revert NotAuthorized();
        _;
    }

    modifier onlyCallbackSender(address reactive_) {
        if (reactive_ != _CALLBACK_SENDER) revert CallbackNotAuthorized();
        _;
    }

    /// @notice Called by the callback proxy to collect payment for delivery.
    function pay(uint256 amount_) external onlyServiceProvider {
        (bool ok,) = payable(_CALLBACK_PROXY).call{ value: amount_ }("");
        require(ok, "pay failed");
    }

    receive() external payable virtual { }
}
