# XProd
A collection of solutions for common production-style problems.

## Production types
1. Discrete - An+Bn+Cn -> Xn+Yn+Zn
Production happens in steps Each step, all inputs are consumed and all outputs produced.
2. Continuous - Same formula, but support every timestep.
A key difficulty with this approach is that it's sensitive to change.
For example, let's say we have: A\*1 -> B\*7
If there is any method to turn this production on an off, there might be a way to get free output.
Avoid that exploit by offsetting the production and consumption times, such that production is delayed long enough.
3. Stock - Input can be added fast, output is gradual. Can optionally spend input.

## Constraints
Each production type should support simulated parallelism.
I.e. when simulating farming, one plot could do: 10 grain -> 17 grain.
Simulating this without keeping track of specific plots, an easy mistake to make would be handling them iteratively.
However, that would turn it into 10 grain -> 17\*plots grain.
While the correct solution would be 10\*plots grain -> 17\*plots grain.

## Open questions
How to simulate a set of identical discrete machines with a continuous formula?
I.e. let's say the discrete machines are plots of land that turn food into more food.
In a discrete setting, all their inputs and outputs could be batched, thus requiring more input for more plots.
With a continuous formula, the trivial solution would remove the need for extra inputs.
Perhaps the stock logic is best here. The inertia of production could essentially be a parameter of its own.
I.e. how much time you need to cover in terms of input to get full output.