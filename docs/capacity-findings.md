# What happens when a governance layer is overloaded

A governance layer sits in front of every action an agent takes. If it cannot keep up, it has to
choose: let actions through unchecked, or refuse them. This edition's engine fails closed when a
policy crashes. The full edition of the engine goes further and also fails closed when it is
overloaded: a call that cannot be checked in time is denied, never allowed.

That choice has a price, and this page shows how big it is. The measurements below come from the
full edition of the engine. That code is not published here. The method and the numbers are.

## The question
Calls arrive at random. Each call is checked by one policy that takes 300 milliseconds. How often
is a call denied only because the layer is busy?

## What was measured
| Calls arriving per second | Default limit (4 at once): measured | Default limit: predicted | Limit raised to 16 at once: measured | Limit of 16: predicted |
|---|---|---|---|---|
| 5 | 5.3% | 4.8% | 0.0% | 0.0% |
| 10 | 20.4% | 20.6% | 0.0% | 0.0% |
| 25 | 57.5% | 55.2% | 0.4% | 0.3% |
| 50 | 75.9% | 75.3% | 16.8% | 14.5% |
| 100 | 87.8% | 87.1% | 53.2% | 49.7% |

- **Measured** is the average of two runs of 280 counted calls each.
- **Predicted** is the Erlang B formula, the standard result for a system that turns away callers when
  all its slots are busy. It needs only two inputs: the arrival rate and the time each call takes.

## What it shows
1. **The default is safe, not free.** With the default limit, one call in five is denied at 10 calls
   per second. Nothing is wrong with the layer. It is doing what it was told, which is to say no when
   it cannot check in time.
2. **The prediction works.** Across all 70 single-policy test cells, 2,530 denials were observed and
   2,461 were expected once the actual arrival rates are used. That is 2.8% more than predicted.
3. **A sizing rule held up.** Take the load, `a = calls per second × seconds per call`, and set the
   limit at `a + 3 × √a`, rounded up. In 10 test cells, 9 had at most 0.4% of calls denied. One had
   2.1%, above the 1% target. Three reruns of that cell gave between 0.0% and 0.7%, so it was
   probably a bad draw, but the rule is supported, not proven, at that point.
4. **Fail fast matters when a policy is marked to skip.** With five policies of 300 milliseconds each,
   a denied call still ran the later policies, taking about one second (0.9 to 1.2 seconds) to be refused. When the later
   policies were marked to be skipped after a denial, a denied call was refused in under 2
   milliseconds, and the share of calls denied at 10 per second fell from 62% to 19%.

## Where the prediction fails
- The formula uses the nominal arrival rate. The random arrivals actually run were up to 14% faster
  than nominal in some cells, which pushes the real denial rate up.
- Three cells were above the prediction by more than chance: one with 150-millisecond calls, a limit of 16
  and 100 calls per second (22% measured against about 15%), one with 50-millisecond calls at 10 per second (3
  denials against 0.3 expected), and the 2.1% cell above. The cause is not established.

## Limits of this measurement
- The policies were stand-ins that wait for a fixed time. They do not model heavy computation or real
  model calls.
- One machine (10 logical cores), one Python version (3.14.7), one process.
- 300 calls per cell, 20 discarded as warm-up, 280 counted. Main cells were run twice, the rest once.
- Percentages come with a normal-approximation interval in the source data. Cells with no denials
  have a true rate that could still be up to about 1.3%.

## What to take from it
Sizing a governance layer is an engineering problem you can calculate, then check. Decide the limit
from your traffic and the time each check takes, then measure. Do not guess.
