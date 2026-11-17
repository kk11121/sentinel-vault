// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title VerdictRegistry — where the off-chain AI worker posts its verdicts.
/// @notice Deployed on Base Sepolia next to the main vault. Only the
///         verdictWriter key may post; it holds no other power anywhere in
///         the system (it cannot move funds or freeze anything directly —
///         the worst a leaked verdictWriter can do is cause freezes, and
///         the recovery path in the README undoes that in 4 transactions).
///         Each (chainId, vault, requestId) accepts exactly ONE verdict:
///         a duplicate post reverts. This makes a restarted worker harmless
///         — it cannot re-judge a request and feed the RSC's escalation
///         counter twice for the same withdrawal.
contract VerdictRegistry {
    uint8 public constant SEVERITY_LOW = 0;
    uint8 public constant SEVERITY_MEDIUM = 1;
    uint8 public constant SEVERITY_HIGH = 2;

    address public owner;
    address public verdictWriter;

    // keccak256(abi.encode(chainId, vault, requestId)) => verdict exists
    mapping(bytes32 => bool) public verdictSeen;

    event VerdictPosted(
        uint256 indexed chainId,
        address indexed vault,
        uint256 indexed requestId,
        uint8 severity,
        uint256 score,
        bytes32 featuresHash,
        bytes32 modelHash
    );
    event VerdictWriterChanged(address indexed oldWriter, address indexed newWriter);

    error NotOwner();
    error NotVerdictWriter();
    error BadSeverity();
    error DuplicateVerdict();

    constructor(address owner_, address verdictWriter_) {
        owner = owner_;
        verdictWriter = verdictWriter_;
    }

    function setVerdictWriter(address newWriter_) external {
        if (msg.sender != owner) revert NotOwner();
        emit VerdictWriterChanged(verdictWriter, newWriter_);
        verdictWriter = newWriter_;
    }

    function verdictKey(uint256 chainId_, address vault_, uint256 requestId_) public pure returns (bytes32) {
        return keccak256(abi.encode(chainId_, vault_, requestId_));
    }

    function hasVerdict(uint256 chainId_, address vault_, uint256 requestId_) external view returns (bool) {
        return verdictSeen[verdictKey(chainId_, vault_, requestId_)];
    }

    /// @notice Post one verdict. The worker posts a verdict for EVERY
    ///         withdrawal request, including LOW ones, so the full decision
    ///         trail is on-chain and replayable.
    function postVerdict(
        uint256 chainId_,
        address vault_,
        uint256 requestId_,
        uint8 severity_,
        uint256 score_,
        bytes32 featuresHash_,
        bytes32 modelHash_
    ) external {
        if (msg.sender != verdictWriter) revert NotVerdictWriter();
        if (severity_ > SEVERITY_HIGH) revert BadSeverity();
        bytes32 key = verdictKey(chainId_, vault_, requestId_);
        if (verdictSeen[key]) revert DuplicateVerdict();
        verdictSeen[key] = true;
        emit VerdictPosted(chainId_, vault_, requestId_, severity_, score_, featuresHash_, modelHash_);
    }
}
