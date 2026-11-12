# Farm discrepancy diagnostics

First 32 seeds in every condition. Alternatives are diagnostic only; neither was adopted.

| Profile | Farm | Default error | No collisions | Full initial buffer |
|---|---|---:|---:|---:|
| none | near | -3.533% | -2.154% | -3.095% |
| none | outer | -2.070% | -0.715% | -1.662% |
| wheelbarrow | near | 1.774% | 2.696% | 1.998% |
| wheelbarrow | outer | 0.574% | 1.516% | 0.733% |

Removing collisions reduces the baseline underestimate but increases the Wheelbarrow overestimate. A full initial buffer does not resolve either. Neither single change satisfies all cases.

Next evidence needed: actual collisions, carry amounts at work-stop changes, and drop-off/return trajectories.
