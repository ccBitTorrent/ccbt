import sys

sys.path.append(".")
import hashlib
import time

from ccbt.piece_manager import PieceManager

# Create test data
test_data = b"test_piece_data" + b"x" * 1000
correct_hash = hashlib.sha1(test_data).digest()

simple_torrent_data = {
    "pieces_info": {
        "num_pieces": 1,
        "piece_length": len(test_data),
        "piece_hashes": [correct_hash],
    },
    "file_info": {
        "total_length": len(test_data),
    },
}

print("Creating PieceManager...")
manager = PieceManager(simple_torrent_data)
manager.test_mode = True

print("Disabling callbacks...")
manager.on_piece_completed = None
manager.on_piece_verified = None
manager.on_file_assembled = None
manager.on_download_complete = None

print("Testing hash verification...")
start_time = time.time()
manager.handle_piece_block(0, 0, test_data)
end_time = time.time()

print("Checking piece state...")
piece = manager.pieces[0]
print(f"Piece state: {piece.state}")
print(f"Hash verified: {piece.hash_verified}")
print(f"Expected hash: {correct_hash.hex()}")
print(f"Completed pieces: {manager.completed_pieces}")
print(f"Verified pieces: {manager.verified_pieces}")
print(f"Test completed in {end_time - start_time:.4f} seconds!")
