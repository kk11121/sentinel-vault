// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @notice LogRecord as delivered to react() by the Omni system contract.
///         Field order per https://dev.reactive.network/reactive-contracts
struct LogRecord {
    uint256 chainId;
    address contractAddress;
    uint256 topic0;
    uint256 topic1;
    uint256 topic2;
    uint256 topic3;
    bytes data;
    uint256 blockNumber;
    uint256 opCode;
    uint256 blockHash;
    uint256 txHash;
    uint256 logIndex;
}

interface IReactive {
    function react(LogRecord memory log_) external;
}
