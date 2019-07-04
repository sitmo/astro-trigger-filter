import random

import sys
sys.path.append("..") # Adds higher directory to python modules path.
from astrotf.radio_pulse import RadioPulseFilterGen

N = 1000 # Number of random triggers
freq_lo_mhz = 1249.8
freq_hi_mhz = 1549.8

# Generate random trigger data
start_times = [random.uniform(0.0, 1.0) for _ in range(N)]
widths = [random.uniform(0.00, 0.01) for _ in range(N)]
DMs = [random.uniform(0.0, 100.0) for _ in range(N)]
SNRs = [random.uniform(5.0, 10.0) for _ in range(N)]

# Reformat data into a list of tuples
triggers = [t for t in zip(start_times, widths,DMs, SNRs)]

# Make sure the list is sorted on start time
# aditional reverse sorting on DM improves the effiency
triggers.sort(key=lambda tup: (tup[0], -tup[2]))


# Itialize the filter generator
gen = RadioPulseFilterGen(freq_lo_mhz, freq_hi_mhz)

# Apply the filter to the list of triggers and print results
for filtered_trigger in gen(triggers):
    print(filtered_trigger)

print('Filtered {} triggers out of a set of {}'.format(gen.num_out, gen.num_in))