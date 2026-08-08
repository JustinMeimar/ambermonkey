
This should seek to quantify the indirection overhead of using
AmberMonkey. A fair comparison is:

1. Regular Baseline tier with ion disabled, WASM disabled
   and the Regex compiler disabled.

2. AmberMonkey running --aot-only with an "Oracle corpus", defined
  as a immediate bootstrapping of the dumped corpus, perfect for
  that workload. Also with WASM + regex compiler disabled. 

We should measure on JetStream and Speedometer, similar to AOT corpus
coverage. The user will need to be careful to run the analyze_speed.py
and `analyze_jetstream.py` scripts on the records from proper variants.
It should ouptut some data, from which a figure script can produce a
horizontal bar graph with error bars.



