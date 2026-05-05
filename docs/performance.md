# Performance

## Memory Backend

Best for small and medium inputs. It uses dictionaries and sets internally.

Expected complexity:

- time: `O(n + m)`;
- memory: `O(n + m)`.

## SQLite Backend

Best default disk backend. It avoids optional dependencies and uses indexes.

Expected behavior:

- slower than memory backend;
- stable and portable;
- good for file/generator inputs.

## Hash Partitioning

Best when you want partition-by-partition processing.

Performance depends on:

- partition count;
- token distribution;
- disk speed;
- serialization cost.

## External Sort

Best when sorted chunk processing is desirable.

Performance depends on:

- chunk size;
- number of chunks;
- merge cost;
- disk speed.

## Practical Tips

- Use memory mode for small data.
- Use SQLite disk mode first for large data.
- Try hash partitioning when one large SQLite index is undesirable.
- Try external sort when chunked sorting fits your workload.
- Use file result mode for large outputs.
