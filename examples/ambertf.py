import matplotlib.pyplot as plt
import pandas as pd
import glob
import sys

sys.path.append("..")  # Adds higher directory to python modules path.
from astrotf.radio import FilterEngine

# observation
freq_lo_mhz = 1249.8
freq_hi_mhz = 1549.8
sample_time = 8.192e-05

# Default set of files to process
file_mask = "CB??.trigger"

# or use one specified by the command line argument
if len(sys.argv) > 1:
    file_mask = sys.argv[1]

print('file mask:', file_mask)

def read_trigger_file(filename, verbose=True):
    if verbose:
        print('start reading:', filename)

    # First read the header line, and extract column names
    with open(filename, "r") as f:
        header = f.readline()

        # correct some column name that have spaces
        header = header.lower().replace(" (s)", "")

        # remove pultiple spaces
        header = ' '.join(header.split())

        # split on space
        colnames = header.strip().split(' ')

        # remove '#' is
        if colnames[0] == '#':
            colnames.pop(0)

    # Read the data
    triggers = pd.read_csv(
        filename,
        delim_whitespace=True,
        names=colnames,
        skiprows=1,
        header=None,
        comment='#'
    )

    # fix column names some more
    triggers.rename(index=str, inplace=True, columns={
        "beam": "beam_id",
        "batch": "batch_id",
        "sample": "sample_id",
        "sigma": "snr"
    })

    if verbose:
        print('finished reading:', filename)

    return triggers


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------

# Process and read all trigger files
input_chunk = []
for filename in glob.glob(file_mask):
    input_chunk.append( read_trigger_file(filename) )

# merge the files into a big one
data = pd.concat(input_chunk, axis=0, ignore_index=True)
print('Read {} triggers'.format(data.shape[0]))

# enrich the data
data['w'] = data.integration_step * sample_time


# Process trigger of individual widths
output_chunks = []
widths = data.w.unique()
for w in widths:

    dataw =  data.loc[data['w'] == w].copy()
    print('start processing: {} triggers of width {}'.format(dataw.shape[0], w))

    eng = FilterEngine(freq_lo_mhz, freq_hi_mhz, buffer_size=512, nn_size=32, tol=1E-4)
    eng.sort(dataw, ['time', 'w', 'dm'])

    output_df = pd.DataFrame(
        [
            t for t in eng.filter(
                (
                    e.time,
                    e.w,
                    e.dm,
                    e.snr,
                    e.beam_id,
                    e.sample_id,
                    e.integration_step
                ) for e in dataw.itertuples()
            )
        ],
        columns=[
            'time',
            'w',
            'dm',
            'snr',
            'beam_id',
            'sample_id',
            'integration_step'
        ]
    )

    output_chunks.append(output_df)
    print('finished processing:', eng.num_in, "->", eng.num_out)


output = pd.concat(output_chunks, axis=0, ignore_index=True)
print("Merged individual files, we now have {} triggers".format(output.shape[0]))

print('final round ...')
eng = FilterEngine(freq_lo_mhz, freq_hi_mhz, buffer_size=512, nn_size=16, tol=1E-4)
eng.sort(output, ['time', 'w', 'dm'])

output_round2 = pd.DataFrame(
    [
        t for t in eng.filter(
        (
            e.time,
            e.w,
            e.dm,
            e.snr,
            e.beam_id,
            e.sample_id,
            e.integration_step
        ) for e in output.itertuples()
    )
    ],
    columns=[
        'time',
        'w',
        'dm',
        'snr',
        'beam_id',
        'sample_id',
        'integration_step'
    ]
)
print('finished processing:', eng.num_in, "->", eng.num_out)
output_round2.to_csv('clean.trigger', sep=" ", index=False)
print("results written to 'clean.trigger'.\ndone.")



fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(22,14), sharex=True, sharey=True)
ax1.scatter(
    data.time,
    data.dm,
    s=20,
    lw=0,
    c='k',
    alpha=1
)
ax2.scatter(
    output_round2.time,
    output_round2.dm,
    s=20,
    lw=0,
    c='k',
    alpha=1
)
ax1.set_ylabel('DM')
ax1.set_xlabel('time (s)')

ax1.set_title('input {}'.format(data.shape[0]))
ax2.set_title('output {}'.format(output_round2.shape[0]))

ax1.set_yscale('log')
ax2.set_yscale('log')

ax1.set_ylim(0.1, 4000)
ax2.set_ylim(0.1, 4000)

plt.tight_layout()
plt.savefig('ambertf.png')