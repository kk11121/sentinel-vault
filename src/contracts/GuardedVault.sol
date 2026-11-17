// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniCallback } from "../base/OmniCallback.sol";

/// @title GuardedVault — vault with a timelock queue watched by the Sentinel.
/// @notice Flow: deposits are free. Withdrawals at or above `largeThreshold`
///         enter a waiting queue and become executable by anyone after
///         `waitSeconds` (fail-open: silence from the AI never blocks them).
///         Below the threshold they are executable immediately. A Reactive
///         callback can veto a queued withdrawal (MEDIUM verdict) or freeze
///         the whole vault (HIGH verdict). freeze/veto are reachable only
///         through this chain's callback proxy with the Sentinel RSC as the
///         injected sender — the AI's key can never call them directly.
contract GuardedVault is OmniCallback {
    struct Withdrawal {
        address requester;
        address to;
        uint256 amount;
        uint256 readyAt;
        bool vetoed;
        bool executed;
    }

    address public owner;
    bool public frozen;
    uint256 public waitSeconds;
    uint256 public largeThreshold;
    uint256 public nextRequestId = 1;

    mapping(uint256 => Withdrawal) public withdrawals;

    event Deposited(address indexed from, uint256 amount);
    event WithdrawalRequested(
        uint256 indexed requestId, address indexed requester, address indexed to, uint256 amount, uint256 readyAt
    );
    event WithdrawalExecuted(uint256 indexed requestId, address indexed to, uint256 amount);
    event WithdrawalVetoed(uint256 indexed requestId, address indexed reactive);
    event Frozen(address indexed reactive, bytes32 reasonCode);
    event Unfrozen(address indexed by);
    event WaitUpdated(uint256 waitSeconds);
    event ThresholdUpdated(uint256 largeThreshold);

    error NotOwner();
    error VaultFrozen();
    error InsufficientBalance();
    error UnknownRequest();
    error AlreadyExecuted();
    error Vetoed();
    error NotReady();
    error AlreadyFrozen();
    error TransferFailed();

    constructor(
        address owner_,
        address callbackProxy_,
        address callbackSender_,
        uint256 waitSeconds_,
        uint256 largeThreshold_
    ) payable OmniCallback(callbackProxy_, callbackSender_) {
        owner = owner_;
        waitSeconds = waitSeconds_;
        largeThreshold = largeThreshold_;
    }

    function deposit() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    function setWait(uint256 waitSeconds_) external {
        if (msg.sender != owner) revert NotOwner();
        waitSeconds = waitSeconds_;
        emit WaitUpdated(waitSeconds_);
    }

    function setThreshold(uint256 largeThreshold_) external {
        if (msg.sender != owner) revert NotOwner();
        largeThreshold = largeThreshold_;
        emit ThresholdUpdated(largeThreshold_);
    }

    /// @notice Queue a withdrawal. Large ones wait; small ones are ready now.
    /// @return requestId The per-vault request id the worker/RSC refer to.
    function requestWithdrawal(address to_, uint256 amount_) external returns (uint256 requestId) {
        if (frozen) revert VaultFrozen();
        if (amount_ > address(this).balance) revert InsufficientBalance();
        requestId = nextRequestId++;
        uint256 readyAt = amount_ >= largeThreshold ? block.timestamp + waitSeconds : block.timestamp;
        withdrawals[requestId] = Withdrawal({
            requester: msg.sender, to: to_, amount: amount_, readyAt: readyAt, vetoed: false, executed: false
        });
        emit WithdrawalRequested(requestId, msg.sender, to_, amount_, readyAt);
    }

    /// @notice Execute a queued withdrawal after its waiting period.
    ///         Permissionless and fail-open: if nobody vetoed it in time,
    ///         anyone can release it.
    function executeWithdrawal(uint256 requestId_) external {
        if (frozen) revert VaultFrozen();
        Withdrawal storage w = withdrawals[requestId_];
        if (w.amount == 0) revert UnknownRequest();
        if (w.executed) revert AlreadyExecuted();
        if (w.vetoed) revert Vetoed();
        if (block.timestamp < w.readyAt) revert NotReady();
        w.executed = true;
        (bool ok,) = payable(w.to).call{ value: w.amount }("");
        if (!ok) revert TransferFailed();
        emit WithdrawalExecuted(requestId_, w.to, w.amount);
    }

    /// @notice Veto one queued withdrawal. Callback-only (MEDIUM verdict).
    function veto(address reactive_, uint256 requestId_)
        external
        onlyServiceProvider
        onlyCallbackSender(reactive_)
    {
        Withdrawal storage w = withdrawals[requestId_];
        if (w.amount == 0) revert UnknownRequest();
        if (w.executed) revert AlreadyExecuted();
        w.vetoed = true;
        emit WithdrawalVetoed(requestId_, reactive_);
    }

    /// @notice Freeze this vault. Callback-only (HIGH verdict).
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
}
