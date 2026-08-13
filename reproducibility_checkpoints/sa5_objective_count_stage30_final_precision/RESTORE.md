# SA5 Stage-30 final precision validated inputs

The chunks contain the exact M5D inputs used by the unique Stage-30 precision execution.

- Archive SHA-256: `458d97b5c825d0eca664a58ff35f07f518e3968d333ae436e720bf8f36ce11f5`
- Chunk count: `2`
- Stage-20 reconstructed SHA-256: `7f7665d3ec870b8d22e51eb69bea9432eb6c2255eb30b077e9df3092dae7713c`
- Stage-30 combined SHA-256: `6542c6c014b99a2a6db08ca1bb54e41c0712643f5e342f3d51ed6826eca49ae5`

Reconstruct with:

```bash
cat chunks/sa5_stage30_validated_inputs.tar.gz.part* > /tmp/sa5_stage30_validated_inputs.tar.gz
echo '458d97b5c825d0eca664a58ff35f07f518e3968d333ae436e720bf8f36ce11f5  /tmp/sa5_stage30_validated_inputs.tar.gz' | sha256sum -c -
tar -xzf /tmp/sa5_stage30_validated_inputs.tar.gz -C /tmp
```
