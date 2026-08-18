# PRE Project — Locked Experimental Principles

Date locked: 2026-08-05
Owner: Siamak

## Principle 1 — Meaning of Random (critical)

The unqualified label **Random** always means **Random-Raw**:

- blind trial-and-error over uniformly sampled odd candidates;
- every sampled odd candidate goes directly to Miller–Rabin;
- no sieve or small-prime filter;
- no wheel;
- no training;
- no memory or catalogue;
- no hidden prior search or oracle work;
- no information copied from PRE, PEE, or another model.

Any random method that receives mathematical filtering or model information must
be named explicitly and must never be reported simply as Random. Examples:

- `Random-Filtered`
- `Random-Wheel`
- `Random-Memory`

These are separate experimental methods, not the Random baseline.

## Principle 2 — Real Miller accounting

- One odd candidate entering Miller–Rabin modular exponentiation equals one
  `MILLER_CALL`.
- `MILLER_BASE_ROUNDS` is reported separately.
- Sieve, wheel, memory, training, fallback, and verification work must not be
  hidden inside another label.
- Online Miller cost and offline/training cost must be reported separately and,
  when end-to-end cost is discussed, combined explicitly.

## Principle 3 — Comparison contract

The primary battle is:

`PRE vs Random-Raw`

This measures the total reduction in real Miller calls versus blind
trial-and-error. Comparisons against filtered random variants are secondary
ablation tests used only to identify which PRE component creates the gain.

## Principle 4 — Architecture integrity

- Preserve the declared PRE configuration during a comparison.
- Use the same digit size, round count, seed policy, Miller bases, and probable-
  prime acceptance rule for both sides unless a difference is explicitly part
  of the experiment.
- Never silently change architecture, accounting, baseline definitions, or
  reuse current-answer information.

## Current PRE-AP Golden configuration

- `FILTER_BOUND = 19997`
- `SEGMENT_ODDS = 256`
- `MILLER_BASES = (2, 3, 5, 7, 11, 13, 17)`
- no training, memory, or current-answer leakage
- output: probable prime under the configured Miller–Rabin bases

## Latest controlled PRE results (200 independent starts per size)

| Digits | Average Miller calls |
|---:|---:|
| 100 | 13.830 |
| 200 | 29.130 |
| 300 | 43.445 |
| 400 | 59.805 |
| 500 | 63.880 |
| 600 | 86.510 |

Empirical fit over 100–600 digits:

`AVG_PRE_MILLER ≈ 0.1383 × DIGITS + 1.03` (`R² ≈ 0.982`)

## Controlled battle — PRE versus Random-Raw

Battle conditions:

- 200 independent prime-generation rounds per digit size
- seed 431
- identical Miller–Rabin bases and probable-prime acceptance rule
- Random-Raw samples uniform odd candidates and sends every candidate directly
  to Miller–Rabin
- Random-Raw uses no sieve, trial division, wheel, training, memory, catalogue,
  hidden search, or PRE output

| Digits | PRE avg Miller | Random-Raw avg Miller | Miller reduction | PRE avg ms | Random-Raw avg ms |
|---:|---:|---:|---:|---:|---:|
| 100 | 13.830 | 119.430 | 8.64x | 3.917 | 23.546 |
| 200 | 29.130 | 219.215 | 7.53x | 30.711 | 205.167 |
| 300 | 43.445 | 343.140 | 7.90x | 121.550 | 854.473 |
| 400 | 59.805 | 435.950 | 7.29x | 336.401 | 2380.466 |
| 500 | 63.880 | 611.095 | 9.57x | 651.112 | 5932.548 |
| 600 | 86.510 | 641.125 | 7.41x | 1446.005 | 10374.715 |

Controlled conclusion:

- PRE used fewer real candidate-level Miller calls than Random-Raw at every
  tested size from 100 through 600 digits
- the observed reduction ranged from 7.29x to 9.57x
- PRE was also faster in total measured engine time at every tested size
- this establishes superiority over blind Random-Raw only
- it does not establish superiority over a matched standard pre-sieve or
  segmented-sieve implementation

## Serial PRE remainder sweep

Architecture tested:

- PRE1 completes 1000 independent rounds
- each terminal PRE1 segment has 256 odd positions and numeric width 512
- after PRE1 finds its prime the unused suffix of that terminal segment is saved
- PRE2 starts only after all PRE1 rounds finish
- PRE2 searches only each saved unused suffix
- no candidate at or before the PRE1 prime is retested
- 100-digit and 200-digit experiments are independent

| Digits | PRE1 avg Miller | Avg unused odd positions | PRE2 successes | PRE2 success rate | PRE2 avg Miller all rounds | Candidate overlap |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 12.864 | 169.023 | 727 of 1000 | 72.7% | 9.291 | 0 |
| 200 | 26.729 | 150.823 | 433 of 1000 | 43.3% | 11.787 | 0 |

Interpretation:

- the saved terminal-segment remainder frequently contains a second probable
  prime at 100 digits
- the same opportunity remains at 200 digits but its success rate is lower
- PRE2 consumes no repeated candidate-level Miller calls
- this experiment measures productive reuse of unsearched range rather than
  prime-location prediction

## Two simultaneous PRE workers at 100 digits

Architecture tested:

- 1000 independent 100-digit rounds
- two workers share one PRE search and never test the same candidate
- sieve survivors are distributed alternately between worker A and worker B
- each parallel wave allows both workers to test one candidate
- both workers stop after the wave that discovers the first probable prime

Logical parallel result:

| Metric | Result |
|---|---:|
| Average total Miller calls | 13.417 |
| Average worker A Miller calls | 6.731 |
| Average worker B Miller calls | 6.686 |
| Average parallel waves | 6.731 |
| Median parallel waves | 5 |
| Ideal Miller-stage latency reduction | 1.99x |
| Two-prime terminal waves | 49 of 1000 |

Measured implementation result:

| Implementation | Total time for 1000 rounds | Average time per prime |
|---|---:|---:|
| One PRE worker | 3.346 seconds | 3.346 ms |
| Two concurrent Python threads | 4.535 seconds | 4.535 ms |

Interpretation:

- two workers nearly halve the number of sequential Miller waves
- total Miller consumption rises from 12.864 to 13.417 because a second call
  can already be in flight during the successful wave
- at 100 digits Python thread scheduling overhead is larger than the saved
  Miller latency
- therefore two concurrent threads are 35.5 percent slower than one PRE worker
  in this measured 100-digit implementation

## Recursive partition test at 100 digits

One thousand identical seeded starts were tested with survivor candidates
distributed without overlap across powers of two logical workers

| Partitions | Halvings | Avg total Miller | Avg Miller per partition | Max partition avg | Avg parallel waves |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 12.864 | 12.864 | 12.864 | 12.864 |
| 2 | 1 | 13.417 | 6.709 | 6.731 | 6.731 |
| 4 | 2 | 14.507 | 3.627 | 3.669 | 3.671 |
| 8 | 3 | 16.762 | 2.095 | 2.151 | 2.156 |
| 16 | 4 | 21.553 | 1.347 | 1.425 | 1.428 |
| 32 | 5 | 31.155 | 0.974 | 1.105 | 1.115 |
| 64 | 6 | 31.774 | 0.496 | 1.016 | 1.094 |
| 128 | 7 | 31.774 | 0.248 | 1.000 | 1.094 |

Conclusion:

- five halvings and 32 partitions reduce the overall average allocation below
  one Miller call per partition
- seven halvings and 128 partitions make every partition average at most one
  Miller call in this test
- partitioning does not reduce total Miller consumption
- total Miller rises because many calls in the successful parallel wave are
  already in flight
- the experiment demonstrates latency distribution rather than computational
  efficiency

## Five halvings with only one Miller call

Clean one-shot architecture:

- construct 32 candidates that survive the configured PRE sieve
- halve the candidate set five times
- select exactly one final survivor without using primality labels or Miller
- send only that survivor to Miller–Rabin
- 1000 independent 100-digit rounds

| Selector | Miller calls per round | Successes | Success rate |
|---|---:|---:|---:|
| Always retain the left half | 1 | 89 of 1000 | 8.9% |
| Neutral start-derived branch | 1 | 70 of 1000 | 7.0% |

Conclusion:

- five halvings can enforce exactly one candidate-level Miller call
- halving alone does not reveal which branch contains a prime
- one-call success is only about 7 to 9 percent under clean non-oracle selection
- selecting the successful branch from primality labels would be current-answer
  leakage or hidden Miller work
- the current PRE therefore cannot simultaneously guarantee one Miller call and
  one probable prime per round

## Clean PEE selector test over 32 PRE survivors

Protocol:

- PRE produces 32 sieve survivors per start without Miller calls
- PEE is trained as a supervised ranker on separate starts
- training uses candidate position local survivor gaps low-bit structure and
  residue metadata but no test labels
- training and test start overlap is zero
- PEE selects exactly one of the 32 candidates on every unseen test start
- only the selected candidate receives the online test Miller call
- two independent one-call controls are measured separately

Training accounting:

| Item | Count |
|---|---:|
| Training starts | 3000 |
| Training candidates | 96000 |
| Explicit training Miller calls | 96000 |
| Training prime rate | 7.8104% |

Unseen one-call test:

| Selector | Test Miller calls | Successes | Success rate |
|---|---:|---:|---:|
| PEE ranker | 1000 | 77 | 7.7% |
| Always first survivor | 1000 | 83 | 8.3% |
| Neutral start-derived survivor | 1000 | 85 | 8.5% |

Conclusion:

- the tested clean PEE ranker did not outperform either one-call control
- no generalizable branch-selection signal was detected
- at 7.7 percent success the implied online retry cost is about 12.99 Miller
  calls per successful prime before adding any training cost
- the experiment provides no evidence that current PEE can reduce the true
  Miller cost to one per successful prime

## PRE chain versus independent starts at 100 digits

Protocol:

- 1000 rounds per mode
- independent mode uses a fresh seeded random odd start each round
- chain mode uses one seeded random start and every discovered probable prime
  becomes the next round start
- identical PRE sieve Miller bases and accounting

| Metric | Independent | Chain |
|---|---:|---:|
| Average Miller calls | 12.864 | 12.637 |
| Median Miller calls | 9 | 9 |
| Miller call percentile 95 | 35 | 38 |
| Maximum Miller calls | 75 | 76 |
| One call success rate | 8.9% | 9.1% |
| Average base rounds | 18.864 | 18.637 |
| Average gap | 222.082 | 224.942 |
| Median gap | 160 | 162 |
| Maximum gap | 1378 | 1596 |
| Average engine time | 3.331 ms | 3.568 ms |

Statistical comparison of average Miller calls:

- chain minus independent difference is minus 0.227 calls
- standard error is 0.533 calls
- approximate two-sided p value is 0.670
- 95 percent confidence interval is minus 1.271 through plus 0.817 calls

Conclusion:

- no statistically significant Miller difference was detected
- chain and independent PRE should currently be treated as equivalent in Miller
  efficiency at 100 digits
- the observed 1.8 percent chain advantage is sampling noise under this test

## Thirty-two-section pool analysis on a 1000-prime chain

Protocol:

- one 100-digit PRE chain of 1000 consecutive rounds
- the first 32 ordered PRE sieve survivors after every chain start are treated
  as the 32 leaves produced by five halvings
- every prime-containing leaf is explicitly labeled and pooled
- pool-label Miller work is reported separately from counterfactual online PRE
  work
- position frequency binary halving paths serial dependence and unseen ranking
  are analyzed

Accounting and pool size:

| Metric | Result |
|---|---:|
| Pool label Miller calls | 32000 |
| Continuation calls beyond the first 32 survivors | 973 |
| Actual analysis Miller calls | 32973 |
| Counterfactual normal online PRE calls | 12637 |
| Prime labels in the pool | 2573 |
| Pool prime rate | 8.0406% |

Pattern results:

- per-section prime rates range from 6.7 percent to 9.4 percent
- the 32-section homogeneity p value is 0.958
- none of the five binary halving decisions has a significant prime-rate split
- selecting the best training section gives 8.2 percent success on the unseen
  half versus a 7.875 percent global unseen candidate rate
- the original chain has a small lag-one winning-section correlation of 0.077
  with p about 0.015

Replication test:

- the lag-one test was repeated on ten independent 1000-round chains
- four correlations are positive and six are negative
- mean correlation is 0.0117 and median correlation is minus 0.0101
- only one of ten chains has p below 0.05 and it is the original chain
- pooled within-chain correlation is 0.0109

Conclusion:

- prime-containing leaves are statistically consistent with equal positional
  probability
- no binary branch from the five halvings is preferred
- the apparent serial effect in the first chain does not replicate
- the pooled sections provide no generalizable prime-location pattern under the
  tested representation

## Filter-bound optimization at 100 digits

Coarse sweep:

- bounds from 97 through 99991 were tested on 1000 identical starts
- every tested bound returned exactly the same probable prime on every start
- reducing the bound changes Miller cost and sieve cost but not the first-prime
  output when the implementation is correct
- the broad timing minimum is in the approximate 12000 through 20000 region

Matched confirmation test:

- bounds 14009 and 19997
- 5000 identical starts
- alternating execution order in 20 matched blocks of 250 starts

| Metric | Bound 14009 | Bound 19997 |
|---|---:|---:|
| Sieve prime count | 1652 | 2261 |
| Average Miller calls | 13.4192 | 12.9536 |
| Mean engine time | 3.4416 ms | 3.4574 ms |
| Median block time | 3.3157 ms | 3.3711 ms |
| Output mismatches | 0 | 0 |

Statistical timing comparison:

- paired mean difference for 14009 minus 19997 is minus 0.0158 ms
- paired p value is 0.672
- no significant total-time difference is detected

Conclusion:

- 19997 is not a unique time optimum
- 14009 reduces the sieve prime table by about 27 percent while preserving all
  tested outputs and statistically equivalent total time
- 19997 retains about 3.6 percent lower Miller consumption
- keep 19997 when candidate-level Miller count is the primary objective
- use 14009 as the current reduced-sieve candidate when table size is the
  primary objective

## Deep-sieve attempt toward one Miller call

Protocol:

- 100 identical 100-digit starts
- segment size remains 256 odd candidates
- filter bounds increase from 19997 through approximately ten million
- output stability Miller calls and complete engine time are measured

| Filter bound | Filter primes | Avg Miller | Median Miller | Avg engine time | Output mismatches |
|---:|---:|---:|---:|---:|---:|
| 19997 | 2261 | 12.58 | 9 | 3.585 ms | 0 |
| 99991 | 9591 | 10.76 | 8 | 4.531 ms | 0 |
| 999983 | 78497 | 9.11 | 7 | 15.410 ms | 0 |
| 9999991 | 664578 | 7.71 | 6 | 113.828 ms | 0 |

Conclusion:

- deeper sieving preserves the returned first probable prime
- Miller calls decline only logarithmically while sieve setup cost grows very
  rapidly
- increasing the bound from 19997 to about ten million removes only about 4.87
  average Miller calls but makes total search time more than 31 times larger
- reaching one Miller by trial-division sieving alone would approach factoring
  candidates up to roughly the square root scale
- for 100-digit candidates that theoretical scale is around ten to the power 50
  and is computationally infeasible
- the tested path cannot economically reduce PRE to one Miller per successful
  prime

## Retained filter configurations

Project decision:

- retain bound 14009 as the practical reduced-sieve PRE configuration
- its approximately one additional Miller call is accepted in exchange for a
  sieve prime table about 27 percent smaller
- all 5000 matched outputs were identical to bound 19997
- retain bound 19997 as the minimum-Miller benchmark and Golden reference
- do not delete or overwrite either configuration

## Filter-bound optimization at 200 digits

Coarse test:

- 200 identical starts
- bounds from 14009 through 999983
- every bound returned identical probable-prime outputs
- the lowest measured time occurred near bound 99991

Matched confirmation:

- 500 identical starts
- five randomized-order blocks
- bounds 70001 99991 130003 and 160001

| Bound | Sieve primes | Avg Miller | Mean time | Median block time | Output mismatches |
|---:|---:|---:|---:|---:|---:|
| 70001 | 6935 | 23.406 | 26.139 ms | 25.476 ms | 0 |
| 99991 | 9591 | 22.712 | 26.010 ms | 24.988 ms | 0 |
| 130003 | 12159 | 22.230 | 26.161 ms | 25.788 ms | 0 |
| 160001 | 14683 | 21.896 | 26.516 ms | 26.131 ms | 0 |

Conclusion:

- the practical 200-digit timing optimum is currently near bound 99991
- larger bounds continue reducing Miller calls but no longer improve total time
- the practical filter bound grows substantially from the retained 100-digit
  bound 14009 to approximately 100000 at 200 digits
- bound 99991 is the current recommended 200-digit practical configuration
  subject to hardware and implementation specific retesting

## Alternating sieve primes after 1000 at 100 digits

Protocol:

- bound remains 14009
- retain every sieve prime through 1000
- after 1000 retain alternating sieve primes through 14009
- both possible alternating offsets are tested
- 1000 identical starts

| Configuration | Sieve primes | Avg Miller | Median Miller | Avg time | Output mismatches |
|---|---:|---:|---:|---:|---:|
| Full 14009 | 1652 | 13.304 | 10 | 3.353 ms | 0 |
| Alternating offset A | 910 | 15.586 | 11 | 3.630 ms | 0 |
| Alternating offset B | 909 | 15.661 | 12 | 3.591 ms | 0 |

Conclusion:

- alternating after 1000 reduces the sieve table by about 45 percent
- returned probable-prime outputs remain identical
- average Miller consumption rises by about 17 percent
- total engine time becomes about 7 percent slower
- this configuration is not retained as a practical PRE improvement

## Second alternating pass after 1000 at 100 digits

Protocol:

- begin with the bound 14009 prime table
- retain every sieve prime through 1000
- apply alternating selection twice to primes after 1000
- equivalently retain one of every four primes after 1000
- test all four possible offsets on 1000 identical starts

| Configuration | Sieve primes | Avg Miller | Median Miller | Avg time | Output mismatches |
|---|---:|---:|---:|---:|---:|
| Full 14009 | 1652 | 13.304 | 10 | 3.368 ms | 0 |
| Quarter offset 0 | 539 | 16.871 | 12 | 3.712 ms | 0 |
| Quarter offset 1 | 538 | 16.962 | 12 | 3.713 ms | 0 |
| Quarter offset 2 | 538 | 16.923 | 12 | 3.694 ms | 0 |
| Quarter offset 3 | 538 | 16.914 | 12.5 | 3.752 ms | 0 |

Conclusion:

- the second alternating pass reduces the full table by about 67 percent
- it adds about 3.57 Miller calls versus the full table
- it adds only about 1.3 Miller calls versus the first alternating pass
- all tested probable-prime outputs remain identical
- total engine time remains worse than the full 14009 sieve

## Intelligent restoration of individual sieve primes

Goal:

- begin with the quarter table containing 539 sieve primes
- restore only empirically useful missing primes
- return unseen average Miller consumption to approximately 13

Clean protocol:

- 2000 separate training starts
- 61800 explicit training Miller calls across full and quarter searches
- score each of the 1113 missing primes by unique composite candidates removed
- restore primes in descending measured marginal utility
- evaluate on 1000 unseen starts

Learned restoration result:

- 991 of 1113 missing primes had to be restored
- smart table size is 1530 versus full size 1652
- smart table is only 7.4 percent smaller than full

| Configuration | Sieve primes | Unseen avg Miller | Median Miller | Output mismatches |
|---|---:|---:|---:|---:|
| Full 14009 | 1652 | 13.327 | 9 | 0 |
| Quarter table | 539 | 17.041 | 12 | 0 |
| Learned noncontiguous table | 1530 | 13.522 | 10 | 0 |
| Smallest-prime prefix of same size | 1530 | 13.476 | 9 | 0 |

Conclusion:

- intelligent noncontiguous selection does not beat the simple smallest-prime
  prefix at equal table size
- smaller sieve primes provide the strongest generalizable marginal utility
- a contiguous prefix through prime 12841 is the best tested 1530-prime compact
  table
- it removes 122 table entries versus full 14009 while keeping average Miller
  near 13
- no special individual-prime pattern beyond small-prime priority is detected

## Alternating Miller calls over PRE survivors

Protocol:

- use the contiguous compact sieve through prime 12841
- 1000 identical independent 100-digit starts
- normal mode sends every sieve survivor to Miller
- alternating modes send only even-rank or odd-rank survivors to Miller
- skipped survivors receive no Miller call

| Mode | Avg Miller | Median Miller | Avg gap | Avg segments | Avg time | Same output as normal |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 13.446 | 10 | 222.082 | 1.094 | 3.249 ms | 1000 |
| Even survivor ranks | 13.280 | 10 | 426.938 | 1.428 | 3.377 ms | 544 |
| Odd survivor ranks | 13.656 | 10 | 457.196 | 1.459 | 3.346 ms | 456 |

Conclusion:

- alternating Miller calls does not halve Miller consumption
- the tested survivor lane retains approximately the same prime probability
- about the same number of actual Miller calls is required to find a prime
- numeric gap nearly doubles because half the valid search stream is skipped
- total engine time is slightly worse because more sieve territory is traversed

## Communication format

When discussing this project with Siamak in Persian:

- do not use punctuation marks in normal chat prose
- avoid mixing Persian and English words on the same line
- code and mathematical expressions are exempt when their syntax requires it
