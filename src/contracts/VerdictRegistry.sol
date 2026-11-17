// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title VerdictRegistry — where the off-chain AI worker posts its verdicts.
/// @notice Deployed on Base Sepolia next to the main vault. Only the
///         verdictWriter key may post; it holds no other power anywhere in
///         the system (it cannot touch funds or freeze anything directly).
contract VerdictRegistry {
    uint8 public constant SEVERITY_LOW = 0;
    uint8 public constant SEVERITY_MEDIUM = 1;
    uint8 public constant SEVERITY_HIGH = 2;

    address public owner;
    address public verdictWriter;

    event VerdictPosted(
        uint256 indexed requestId,
        address indexed vault,
        uint8 severity,
        uint256 score,
        bytes32 featuresHash,
        bytes32 modelHash
    );
    event VerdictWriterChanged(address indexed oldWriter, address indexed newWriter);

    error NotOwner();
    error NotVerdictWriter();
    error BadSeverity();

    constructor(address owner_, address verdictWriter_) {
        owner = owner_;
        verdictWriter = verdictWriter_;
    }

    function setVerdictWriter(address newWriter_) external {
        if (msg.sender != owner) revert NotOwner();
        emit VerdictWriterChanged(verdictWriter, newWriter_);
        verdictWriter = newWriter_;
    }

    /// @notice Post one verdict. The worker posts a verdict for EVERY
    ///         withdrawal request, including LOW ones, so the full decision
    ///         trail is on-chain and replayable.
    function postVerdict(
        uint256 requestId_,
        address vault_,
        uint8 severity_,
        uint256 score_,
        bytes32 featuresHash_,
        bytes32 modelHash_
    ) external {
        if (msg.sender != verdictWriter) revert NotVerdictWriter();
        if (severity_ > SEVERITY_HIGH) revert BadSeverity();
        emit VerdictPosted(requestId_, vault_, severity_, score_, featuresHash_, modelHash_);
    }
}
