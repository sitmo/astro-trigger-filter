import sys

def dm_one_delay(freq_lo_mhz, freq_hi_mhz):
    """Compute the dispersion delay of a DM = 1 signal.

    :param freq_lo_mhz: Lowest frequency in the observation range.
    :type freq_lo_mhz: float
    :param freq_hi_mhz: Highest frequency in the observation range.
    :type freq_hi_mhz: float
    :return: he expected delay (in seconds) between the highest and lowest frequency of a DM=1 signal.
    :rtype: float
    """
    return 4.15E3 * (freq_lo_mhz**-2 - freq_hi_mhz**-2)


class RadioPulseFilterGen:

    def __init__(self, freq_lo_mhz, freq_hi_mhz, tol=1E-4, buffer_size=256, autoflush=True, nn_size=8, max_dm_diff=40):
        """Constructor

        :param freq_lo_mhz: The lowest observation frequency.
        :type freq_lo_mhz: float
        :param freq_hi_mhz: The highest observation frequency.
        :type freq_hi_mhz: float
        :param tol: Tolerance in timing, defaults to 1E-4.
        :type tol: float, optional
        :param buffer_size: Maximum active set buffer size, set to zero for unlimited sizem, defaults to 256
        :type buffer_size: int,optional
        :param nn_size: Size of the nearest neighbourhood, defaults to 8
        :type nn_size: int
        :param autoflush: Automatically flush the active set after finishing.
        :type autoflush: bool, optional
        """
        self.tol = tol
        self.dm1 = dm_one_delay(freq_lo_mhz, freq_hi_mhz)

        self.buffer_size = buffer_size
        self.autoflush = autoflush
        self.nn_size = nn_size
        self.max_dm_diff = max_dm_diff

        # Accumulate Performance Statistics: number of trigger that went in/out.
        self.active_set = []
        self.num_in = 0
        self.num_out = 0
        self.num_evicted = 0

    def reset(self):
        """Reset the statics and state of this class

        :return: None
        """
        self.active_set = []
        self.num_in = 0
        self.num_out = 0
        self.num_evicted = 0

    def unpack(self, item):
        t0_k, w_k, dm_k, snr_k = item[:4]
        b0_k = t0_k + dm_k * self.dm1
        b1_k = b0_k + w_k
        return t0_k, w_k, dm_k, snr_k, b0_k, b1_k
        
    def is_local_max(self, k):
        """Tests if a trigger in the active set is a local maximum

        A trigger in the active set is a local maximum if the smallest wrapping and largest contained
        triggers both don't have a larger SNR

        :param k: the index number of the trigger to test
        :type k: int

        :return: `True` if the k-th trigger in the active set is a local maximum, else `False`
        :rtype: bool
        """
        t0_k, w_k, dm_k, snr_k, b0_k, b1_k = self.unpack(self.active_set[k])

        # analyze elements k-1, k-2,... 0 and stop at the frist element that intersects
        # there element will have deceasing start times, and the start times will be <=
        i = k - 1
        intersect_counter = 0
        while i >= 0:
            t0_i, w_i, dm_i, snr_i, b0_i, b1_i = self.unpack(self.active_set[i])

            # we only consider triggers closeby in DM space
            if abs(dm_k - dm_i) <= self.max_dm_diff:

                if b1_i + self.tol >= b0_k:
                    intersect_counter += 1
                    if snr_i >= snr_k:
                        return False  # our left neighbor is bigger
                if intersect_counter >= self.nn_size:
                    break  # we have found enough left neighbour
            i -= 1

        i = k + 1
        intersect_counter = 0
        while i < len(self.active_set):
            t0_i, w_i, dm_i, snr_i, b0_i, b1_i = self.unpack(self.active_set[i])

            if abs(dm_k - dm_i) <= self.max_dm_diff:
                if b1_i <= b1_k + self.tol:
                    intersect_counter += 1
                    if snr_i >= snr_k:
                        return False
                if intersect_counter >= self.nn_size:
                    break  # we have found enough right neighbour
            i += 1

        # if none of our neighbours was bigger then WE are the local max
        return True

    def __call__(self, expression):
        """Generator function that filters a list of elements

        :param expression:
        :type expression: An iterable object of elements where the first four values are (t', 'w', 'DM', 'SNR', ...)
        :return: An iterator for a subset of the the elements.
        """
        # Input a list of tuples: [ (t, w, dm, snr), ... ]

        # The main loop, we process items from an iterable object
        it = expression.__iter__()

        # Support both Python 2 and 3
        if sys.version_info > (3, 0):
            def get_next(iterator):
                return iterator.__next__()
        else:
            def get_next(iterator):
                return iterator.next()

        while True:

            try:
                # Get the next item
                item_i = get_next(it)
                t0_i, w_i, dm_i, snr_i, b0_i, b1_i = self.unpack(item_i)

                self.num_in += 1

                # compare the current trigger against all triggers in the active set, test for expiration
                yield_set = []
                remove_set = []

                for k in range(len(self.active_set)):

                    # get the k-th trigger data from the active set
                    item_k = self.active_set[k]
                    t0_k, w_k, dm_k, snr_k, b0_k, b1_k = self.unpack(item_k)

                    # Check if trigger #k has expired. If so: remove and possibly yield
                    if b1_k < t0_i:
                        remove_set.append(k)

                        if self.is_local_max(k):
                            yield_set.append(k)

                # yield expired local maxima
                for k in yield_set:
                    self.num_out += 1
                    yield self.active_set[k]

                # remove expired triggers
                for k in remove_set[::-1]:
                    del self.active_set[k]

                # make sure we don't have too many items in the buffer
                if self.buffer_size > 0:  # do we have a buffer_size limit?

                    while len(self.active_set) >= self.buffer_size:  # while not enough room
                        item_0 = self.active_set[0]
                        to_be_yielded = self.is_local_max(0)

                        self.num_evicted += 1
                        del self.active_set[0]

                        if to_be_yielded:
                            self.num_out += 1
                            yield item_0

                # After removing expired elements and from the active set, we join the set
                self.active_set.append(item_i)

            except StopIteration:

                # we are done processing triggers, flush the active set
                if self.autoflush:

                    yield_set = []
                    for k in range(len(self.active_set)):
                        if self.is_local_max(k):
                            yield_set.append(k)
                    for k in yield_set:
                        self.num_out += 1
                        yield self.active_set[k]
                break


def radio_pulse_polygon(t0, w, dm, num_steps=100, freq_lo=1249.8046875, freq_hi=1549.8046875):
    """Generate a polygon of a pulse.

    :param t0: Start of the pulse at the top frequency
    :type t0: float
    :param w:  Width of the pulse
    :type w: float
    :param dm: Dispersion measure
    :type dm: float
    :param num_steps: Number of ine segments
    :type num_steps: int
    :param freq_lo: Lowest frequency
    :type freq_lo: float
    :param freq_hi: Highest frequency
    :type freq_hi: float
    :return: A list of vertices of the pulse [ (x0,y0), (x1,x1), ..
    :rtype dm: list of 2d coordinate tuples
    """

    f_step = (freq_hi - freq_lo) / (num_steps - 1)

    v0 = []
    v1 = []

    for i in range(num_steps):
        f_i = freq_hi - i * f_step
        delay_i = dm_one_delay(f_i, freq_hi) * dm
        v0.append((t0 + delay_i, f_i))
        v1.append((t0 + delay_i + w, f_i))

    return v0 + v1[::-1]
