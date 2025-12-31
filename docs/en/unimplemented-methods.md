# Unimplemented Methods

This document tracks methods and features that are declared but not yet fully implemented in ccBitTorrent.

## Purpose

This document serves as a reference for:
- Developers working on feature implementation
- Contributors looking for areas to contribute
- Users understanding the current state of the codebase

## Abstract Methods

### Peer Protocol

- `PeerMessage.encode()` - Base class method, implemented in subclasses
- `PeerMessage.decode()` - Base class method, implemented in subclasses

These are abstract base methods that are properly implemented in concrete subclasses.

## Future Implementations

This section will be updated as new features are planned and implemented.

## Contributing

If you're interested in implementing any of these methods, please:
1. Check existing issues on GitHub
2. Review the relevant BEP (BitTorrent Enhancement Proposal) documentation
3. Follow the [Contributing Guide](contributing.md)
4. Submit a pull request with your implementation

## Notes

- Methods marked with `# pragma: no cover` are abstract methods that cannot be tested directly
- All abstract methods should have concrete implementations in subclasses
- This document is maintained as part of the release checklist process

