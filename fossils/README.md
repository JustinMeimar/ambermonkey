
general principles for creating fossils:

- a fossil is composed of (parser (?), analysis, figure)

- always make figure scripts decoupled from any particular combination
  of variants selected for analysis, within reason. For example,
  suppose we have an experiment with four variants, each for an
  optimization algorithm to evaluate (`opt-A`, `opt-B`, `opt-C`,
  `opt-D`). A figure script, producing either a JSON table or a PDF
  figure, should not hard-code the variant names. Rather they should
  be passed in generically such that, if we decide to emit `opt-B`
  from the evaluation, the scripts don't break.

-

