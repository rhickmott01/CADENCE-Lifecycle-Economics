import argparse
from cadence_lifecycle.hazus import inspect_partition
p=argparse.ArgumentParser();p.add_argument("partition")
a=p.parse_args()
for file,cols in inspect_partition(a.partition).items():
 print(file)
 for col in cols: print("  ",col[0],col[1])
