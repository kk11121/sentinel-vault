// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { OmniCallback } from "../base/OmniCallback.sol";

/// @title GuardedVault — vault with a timelock queue watched by the Sentinel.
/// @notice Key split (see README "Key compromise table"):
///           owner    — the daily key. Deposits and withdrawal REQUESTS only.
///                      It cannot unfreeze, reconfigure, or move funds except
///                      by requesting a withdrawal like any other.
///           recovery — the offline key. The only key that can unfreeze or
///                      change waitSeconds / largeThreshold / instantCap.
///         Withdrawal flow:
///           - Requests are owner-only (a request names its destination at
///             request time; execution is then permissionless and safe).
///           - Amounts at or above `largeThreshold` enter the waiting queue
///             and become executable by anyone after `waitSeconds`
///             (fail-open: silence from the AI never blocks them).
///           - Amounts below the threshold execute immediately, BUT the
///             total that may leave instantly is capped at `instantCap`
///             per `instantWindowSeconds`. Anything past the cap is routed
///             into the waiting queue instead, where the Sentinel can veto
///             it. This closes the "split into small pieces and drain
///             before the verdict arrives" hole.
///           - A Reactive callback can veto a queued withdrawal (MEDIUM
///             verdict) or freeze the whole vault (HIGH verdict).
///             freeze/veto are reachable only through this chain's callback
///             proxy with the Sentinel RSC as the injected sender — the
///             AI's key can never call them directly.
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
    address public recovery;
    bool public frozen;
    uint256 public waitSeconds;
    uint256 public largeThreshold;
    uint256 public instantCap;
    uint256 public instantWindowSeconds;
    uint256 public instantWindowStart;
    uint256 public instantSpentInWindow;
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
    event InstantCapUpdated(uint256 instantCap, uint256 instantWindowSeconds);

    error NotOwner();
    error NotRecovery();
    error VaultFrozen();
    error InsufficientBalance();
    error UnknownRequest();
    error AlreadyExecuted();
    error Vetoed();
    error NotReady();
    error TransferFailed();

    constructor(
        address owner_,
        address recovery_,
        address callbackProxy_,
        address callbackSender_,
        uint256 waitSeconds_,
        uint256 largeThreshold_,
        uint256 instantCap_,
        uint256 instantWindowSeconds_
    ) payable OmniCallback(callbackProxy_, callbackSender_) {
        owner = owner_;
        recovery = recovery_;
        waitSeconds = waitSeconds_;
        largeThreshold = largeThreshold_;
        instantCap = instantCap_;
        instantWindowSeconds = instantWindowSeconds_;
        instantWindowStart = block.timestamp;
    }

    modifier onlyRecovery() {
        if (msg.sender != recovery) revert NotRecovery();
        _;
    }

    function deposit() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    function setWait(uint256 waitSeconds_) external onlyRecovery {
        waitSeconds = waitSeconds_;
        emit WaitUpdated(waitSeconds_);
    }

    function setThreshold(uint256 largeThreshold_) external onlyRecovery {
        largeThreshold = largeThreshold_;
        emit ThresholdUpdated(largeThreshold_);
    }

    function setInstantCap(uint256 instantCap_, uint256 instantWindowSeconds_) external onlyRecovery {
        instantCap = instantCap_;
        instantWindowSeconds = instantWindowSeconds_;
        emit InstantCapUpdated(instantCap_, instantWindowSeconds_);
    }

    /// @notice Queue a withdrawal. Owner-only: the vault guards the owner's
    ///         funds, so only the owner's daily key may name a destination.
    ///         Large amounts wait; small amounts are instant until the
    ///         per-window instant cap is exhausted, then they queue too.
    /// @return requestId The per-vault request id the worker/RSC refer to.
    function requestWithdrawal(address to_, uint256 amount_) external returns (uint256 requestId) {
        if (msg.sender != owner) revert NotOwner();
        if (frozen) revert VaultFrozen();
        if (amount_ > address(this).balance) revert InsufficientBalance();
        requestId = nextRequestId++;
        uint256 readyAt;
        if (amount_ >= largeThreshold) {
            readyAt = block.timestamp + waitSeconds;
        } else if (_consumeInstantBudget(amount_)) {
            readyAt = block.timestamp;
        } else {
            // Instant budget for this window is exhausted: queue instead of
            // refusing, so a burst of small withdrawals becomes visible to
            // the Sentinel instead of draining ahead of its verdicts.
            readyAt = block.timestamp + waitSeconds;
        }
        withdrawals[requestId] = Withdrawal({
            requester: msg.sender, to: to_, amount: amount_, readyAt: readyAt, vetoed: false, executed: false
        });
        emit WithdrawalRequested(requestId, msg.sender, to_, amount_, readyAt);
    }

    function _consumeInstantBudget(uint256 amount_) internal returns (bool) {
        if (block.timestamp >= instantWindowStart + instantWindowSeconds) {
            instantWindowStart = block.timestamp;
            instantSpentInWindow = 0;
        }
        if (instantSpentInWindow + amount_ > instantCap) return false;
        instantSpentInWindow += amount_;
        return true;
    }

    /// @notice Execute a queued withdrawal after its waiting period.
    ///         Permissionless and fail-open: the destination was fixed at
    ///         request time by the owner, so if nobody vetoed it in time,
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
    ///         Idempotent: a duplicate veto, or a veto arriving after
    ///         execution, does not revert — a failed callback would only
    ///         add a confusing Fail entry to the evidence trail.
    function veto(address reactive_, uint256 requestId_)
        external
        onlyServiceProvider
        onlyCallbackSender(reactive_)
    {
        Withdrawal storage w = withdrawals[requestId_];
        if (w.amount == 0 || w.executed) return;
        w.vetoed = true;
        emit WithdrawalVetoed(requestId_, reactive_);
    }

    /// @notice Freeze this vault. Callback-only (HIGH verdict).
    ///         Idempotent: freezing an already-frozen vault is a no-op
    ///         that still emits the event, never a revert.
    function freeze(address reactive_, bytes32 reasonCode_)
        external
        onlyServiceProvider
        onlyCallbackSender(reactive_)
    {
        frozen = true;
        emit Frozen(reactive_, reasonCode_);
    }

    /// @notice Unfreeze. Recovery-key only: the daily (owner) key that a
    ///         freeze is meant to defend against cannot lift the freeze.
    function unfreeze() external onlyRecovery {
        frozen = false;
        emit Unfrozen(msg.sender);
    }
}
