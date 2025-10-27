# Checkpoints Guide

Checkpoints allow resuming downloads. Two formats are supported: JSON and BINARY (.bin/.gz).

## Paths
Default directory: `.ccbt/checkpoints`. Files are named `<infohash>.checkpoint.*`.

## Save & Verify
- Saved automatically during downloads if enabled.
- Verify: `ccbt checkpoints verify <info_hash>`

## Export
```bash
ccbt checkpoints export <info_hash> --format json --output cp.json
```

## Backup & Restore
```bash
ccbt checkpoints backup <info_hash> --destination backup.cp --compress --encrypt
ccbt checkpoints restore backup.cp --info-hash <info_hash>
```

## Migrate
```bash
ccbt checkpoints migrate <info_hash> --from-format json --to-format binary
```
