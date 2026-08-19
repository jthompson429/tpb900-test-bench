from tpb9000_testbench.hardware import Direction, LimitState


class FakeHardware:
    def __init__(self, states):
        self.states = iter(states)
        self.last = LimitState(False, False)
        self.drives = []
        self.stop_count = 0

    def limits(self):
        try:
            self.last = next(self.states)
        except StopIteration:
            pass
        return self.last

    def drive(self, direction: Direction):
        self.drives.append(direction)

    def stop(self):
        self.stop_count += 1

    def close(self):
        self.stop()


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds

