import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
import random

async def monitor_fifo(dut):
    while True:
        await RisingEdge(dut.clk_r)
        r_data = dut.r_data.value.binstr
        print(f"[READ_CLK] r_en={int(dut.r_en.value)} r_data={r_data} empty={int(dut.empty.value)} rq2_wgray={bin(int(dut.rq2_wgray.value))} rgray={bin(int(dut.rgray.value))}")

async def monitor_write(dut):
    while True:
        await RisingEdge(dut.clk_w)
        if dut.w_en.value:
            print(f"[WRITE_CLK] w_en=1 w_data={int(dut.w_data.value)} wbin={bin(int(dut.wbin.value))}")

async def reset_fifo(dut):
    dut.rst_w.value = 0
    dut.rst_r.value = 0
    dut.w_en.value = 0
    dut.r_en.value = 0
    await Timer(50, units='ns')
    dut.rst_w.value = 1
    dut.rst_r.value = 1
    for _ in range(5):
        await RisingEdge(dut.clk_w)
        await RisingEdge(dut.clk_r)

async def write_single(dut, value):
    """Write one value to FIFO if not full."""
    if dut.full.value:
        return False

    dut.w_data.value = value
    dut.w_en.value = 1
    await RisingEdge(dut.clk_w)
    dut.w_en.value = 0
    await RisingEdge(dut.clk_w)
    return True


async def read_single(dut):
    """Read one value from FIFO if not empty."""
    if dut.empty.value:
        return None
    # await RisingEdge(dut.clk_r)
    dut.r_en.value = 1
    await RisingEdge(dut.clk_r)
    await FallingEdge(dut.clk_r)
    value = int(dut.r_data.value)
    print(f"[GENERIC_READ] Read value: {value}")
    dut.r_en.value = 0
    await RisingEdge(dut.clk_r)
    return value

async def drain_fifo(dut, max_reads=32):
    """Continuously read from FIFO until empty or max_reads reached."""
    reads = []
    for _ in range(max_reads):
        while dut.empty.value:
            await RisingEdge(dut.clk_r)

        value = await read_single(dut)
        if value is not None:
            reads.append(value)

        # Check if empty flag is high after read
        await RisingEdge(dut.clk_r)
        if dut.empty.value:
            print("[GENERIC_READ] FIFO empty after draining.")
            break
    else:
        print("[GENERIC_READ] Warning: hit max_reads limit — FIFO may not be empty.")

    return reads


async def write_until_full(dut):
    """Write sequential values until FIFO reports full."""
    value = 0
    result = []

    while True:
        success = await write_single(dut, value)
        if not success:
            break
        result.append(value)
        value += 1

    print(f"[DEBUG] Finished writing {len(result)} items (should match FIFO capacity)")
    return result


async def write_beyond_full(dut, limit=3):
    print("[TEST] Write beyond full (should not write)")
    attempts = 0
    while attempts < limit:
        if dut.full.value:
            dut.w_data.value = 123
            dut.w_en.value = 1
            await RisingEdge(dut.clk_w)
            dut.w_en.value = 0
            print("[DEBUG] Tried writing while full (should be ignored)")
            await RisingEdge(dut.clk_w)
            attempts += 1
        else:
            await RisingEdge(dut.clk_w)

async def read_beyond_empty(dut, limit=3):
    print("[TEST] Read beyond empty (should not read)")
    attempts = 0
    while attempts < limit:
        if dut.empty.value:
            dut.r_en.value = 1
            await RisingEdge(dut.clk_r)
            dut.r_en.value = 0
            print("[DEBUG] Tried reading while empty (should be ignored)")
            await RisingEdge(dut.clk_r)
            attempts += 1
        else:
            await RisingEdge(dut.clk_r)

async def simultaneous_rw(dut):
    write_task = cocotb.start_soon(write_until_full(dut))
    await Timer(200, units="ns")
    read_task = cocotb.start_soon(drain_fifo(dut))
    await write_task
    await read_task

@cocotb.test()
async def test_asynch_fifo(dut):
    cocotb.start_soon(Clock(dut.clk_r, 14, units='ns').start())
    cocotb.start_soon(Clock(dut.clk_w, 18, units='ns').start())

    await reset_fifo(dut)
    # cocotb.start_soon(monitor_fifo(dut))
    # cocotb.start_soon(monitor_write(dut))

    # CASE 1: Write until full
    test_data = await write_until_full(dut)
    print(f"[DEBUG] Finished writing {len(test_data)} items")

    # Try writing beyond full
    await write_beyond_full(dut)

    # CASE 2: Read until empty
    read_values = await drain_fifo(dut)
    print(f"[DEBUG] Drained values: {read_values}")
    assert len(read_values) == len(test_data), f"Mismatch in count: wrote {len(test_data)}, read {len(read_values)}"
    assert read_values == test_data, f"Data mismatch! Expected {test_data}, got {read_values}"


    # Try reading beyond empty
    await read_beyond_empty(dut)

    # CASE 3: Simultaneous read/write
    await reset_fifo(dut)
    test_data = list(range(10, 20))
    await simultaneous_rw(dut)
