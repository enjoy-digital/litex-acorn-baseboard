#
# This file is part of LiteX-Acorn-Baseboard.
#
# SPDX-License-Identifier: BSD-2-Clause

# Minimal gateware-only HTTP server for LiteEth's hardware IP stack (no CPU).
#
# The TCP layer is stateless: every reply is computed from the received segment only, so retransmits
# from the client are naturally handled and any number of clients can be served:
# - SYN               -> SYN+ACK.
# - Segment with data -> ACK+PSH+FIN with the full HTTP response (whatever the request is).
# - FIN               -> ACK.
# - Anything else     -> Ignored.
#
# Limitations: the whole HTTP response must fit in a single TCP segment, requests split over
# multiple segments are answered multiple times and received TCP checksums are not verified.

from migen import *

from litex.gen import *

from liteeth.common import convert_ip

# Constants ----------------------------------------------------------------------------------------

TCP_PROTOCOL      = 0x06
TCP_HEADER_LENGTH = 20
TCP_MAX_PAYLOAD   = 1460 # Ethernet MTU - IPv4 header - TCP header.

TCP_FIN = 0x01
TCP_SYN = 0x02
TCP_RST = 0x04
TCP_PSH = 0x08
TCP_ACK = 0x10

# Helpers ------------------------------------------------------------------------------------------

def http_response(body, content_type="text/html"):
    if isinstance(body, str):
        body = body.encode()
    header  = "HTTP/1.0 200 OK\r\n"
    header += f"Content-Type: {content_type}\r\n"
    header += f"Content-Length: {len(body)}\r\n"
    header += "Connection: close\r\n"
    header += "\r\n"
    return header.encode() + body

def ones_complement_sum(data):
    if len(data) % 2:
        data = data + b"\x00"
    s = sum(int.from_bytes(data[i:i+2], "big") for i in range(0, len(data), 2))
    while s >> 16:
        s = (s & 0xffff) + (s >> 16)
    return s

# LiteEth TCP HTTP Server --------------------------------------------------------------------------

class LiteEthTCPHTTPServer(LiteXModule):
    def __init__(self, ip, ip_address, response, port=80, window=8192):
        ip_address = convert_ip(ip_address)
        response   = bytes(response)
        assert 0 < len(response) <= TCP_MAX_PAYLOAD, "HTTP response must fit in one TCP segment."

        self.ip_port = ip_port = ip.crossbar.get_port(TCP_PROTOCOL, dw=8)
        rx = ip_port.source
        tx = ip_port.sink

        # # #

        # Initial Sequence Number (Free-running counter).
        isn = Signal(32)
        self.sync += isn.eq(isn + 1)

        # RX: Capture TCP header fields of the received segment.
        # ------------------------------------------------------
        rx_count       = Signal(5)
        rx_length      = Signal(16) # TCP segment length (header + payload).
        rx_remote_ip   = Signal(32)
        rx_remote_port = Signal(16)
        rx_local_port  = Signal(16)
        rx_seq         = Signal(32)
        rx_ack         = Signal(32)
        rx_offset      = Signal(4)
        rx_flags       = Signal(8)
        rx_payload_len = Signal(16)

        rx_header_cases = {
             0 : rx_remote_port[8:16].eq(rx.data),
             1 : rx_remote_port[0: 8].eq(rx.data),
             2 : rx_local_port[8:16].eq(rx.data),
             3 : rx_local_port[0: 8].eq(rx.data),
            12 : rx_offset.eq(rx.data[4:8]),
            13 : rx_flags.eq(rx.data),
        }
        for i in range(4):
            rx_header_cases[4 + i] = rx_seq.eq(Cat(rx.data, rx_seq[:24]))
            rx_header_cases[8 + i] = rx_ack.eq(Cat(rx.data, rx_ack[:24]))

        # TX: Reply parameters.
        # ---------------------
        tx_seq      = Signal(32)
        tx_ack      = Signal(32)
        tx_flags    = Signal(8)
        tx_payload  = Signal()
        tx_length   = Signal(16)
        tx_checksum = Signal(16)
        tx_count    = Signal(max=TCP_HEADER_LENGTH + len(response) + 1)

        # Checksum: One's complement sum over IPv4 pseudo-header + TCP header + payload, with all the
        # constant parts precomputed at build time.
        const_sum  = 0
        const_sum += (ip_address >> 16) + (ip_address & 0xffff) # Local IP.
        const_sum += TCP_PROTOCOL + TCP_HEADER_LENGTH           # Protocol / TCP length (header).
        const_sum += port                                       # Local port.
        const_sum += (TCP_HEADER_LENGTH//4) << 12               # Data offset.
        const_sum += window                                     # Window.
        payload_sum = ones_complement_sum(response) + len(response) # Payload / TCP length (payload).
        checksum_words = [
            const_sum,
            rx_remote_ip[16:32], rx_remote_ip[0:16],
            rx_remote_port,
            tx_seq[16:32], tx_seq[0:16],
            tx_ack[16:32], tx_ack[0:16],
            tx_flags,
            Mux(tx_payload, payload_sum, 0),
        ]
        checksum       = Signal(32)
        checksum_count = Signal(max=len(checksum_words) + 1)

        # Response memory.
        mem  = Memory(8, len(response), init=list(response))
        port_rd = mem.get_port(async_read=True)
        self.specials += mem, port_rd
        self.comb += port_rd.adr.eq(tx_count - TCP_HEADER_LENGTH)

        # TX header bytes.
        tx_header = Signal(8)
        self.comb += Case(tx_count, {
             0 : tx_header.eq(port >> 8),
             1 : tx_header.eq(port & 0xff),
             2 : tx_header.eq(rx_remote_port[8:16]),
             3 : tx_header.eq(rx_remote_port[0: 8]),
             4 : tx_header.eq(tx_seq[24:32]),
             5 : tx_header.eq(tx_seq[16:24]),
             6 : tx_header.eq(tx_seq[ 8:16]),
             7 : tx_header.eq(tx_seq[ 0: 8]),
             8 : tx_header.eq(tx_ack[24:32]),
             9 : tx_header.eq(tx_ack[16:24]),
            10 : tx_header.eq(tx_ack[ 8:16]),
            11 : tx_header.eq(tx_ack[ 0: 8]),
            12 : tx_header.eq((TCP_HEADER_LENGTH//4) << 4),
            13 : tx_header.eq(tx_flags),
            14 : tx_header.eq(window >> 8),
            15 : tx_header.eq(window & 0xff),
            16 : tx_header.eq(tx_checksum[8:16]),
            17 : tx_header.eq(tx_checksum[0: 8]),
            "default" : tx_header.eq(0), # Urgent pointer.
        })

        # RX header capture.
        self.sync += If(rx.valid & rx.ready,
            If(rx_count == 0,
                rx_remote_ip.eq(rx.ip_address),
                rx_length.eq(rx.length),
            ),
            Case(rx_count, rx_header_cases),
            If(rx.last,
                rx_count.eq(0)
            ).Elif(rx_count != (2**len(rx_count) - 1),
                rx_count.eq(rx_count + 1)
            )
        )

        # FSM.
        # ----
        self.fsm = fsm = FSM(reset_state="RECEIVE")
        fsm.act("RECEIVE",
            rx.ready.eq(1),
            If(rx.valid & rx.last,
                NextState("CHECK")
            )
        )
        fsm.act("CHECK",
            NextValue(rx_payload_len, rx_length - Cat(Signal(2), rx_offset)),
            # Only accept well-formed segments to our port, ignore resets.
            If((rx_local_port  == port) &
               (rx_length      >= TCP_HEADER_LENGTH) &
               (rx_offset      >= (TCP_HEADER_LENGTH//4)) &
               (Cat(Signal(2), rx_offset) <= rx_length) &
               ((rx_flags & TCP_RST) == 0),
                NextState("DECIDE")
            ).Else(
                NextState("RECEIVE")
            )
        )
        fsm.act("DECIDE",
            NextValue(tx_payload, 0),
            NextValue(checksum,   0),
            NextValue(checksum_count, 0),
            # Connection request: SYN -> SYN+ACK.
            If((rx_flags & (TCP_SYN | TCP_ACK)) == TCP_SYN,
                NextValue(tx_flags, TCP_SYN | TCP_ACK),
                NextValue(tx_seq,   isn),
                NextValue(tx_ack,   rx_seq + 1),
                NextState("CHECKSUM")
            # Request: Data -> ACK+PSH+FIN with HTTP response.
            ).Elif(((rx_flags & TCP_SYN) == 0) & (rx_payload_len != 0),
                NextValue(tx_flags,   TCP_ACK | TCP_PSH | TCP_FIN),
                NextValue(tx_seq,     rx_ack),
                NextValue(tx_ack,     rx_seq + rx_payload_len + ((rx_flags & TCP_FIN) != 0)),
                NextValue(tx_payload, 1),
                NextState("CHECKSUM")
            # Close: FIN -> ACK.
            ).Elif(((rx_flags & (TCP_SYN | TCP_FIN)) == TCP_FIN),
                NextValue(tx_flags, TCP_ACK),
                NextValue(tx_seq,   rx_ack),
                NextValue(tx_ack,   rx_seq + 1),
                NextState("CHECKSUM")
            ).Else(
                NextState("RECEIVE")
            )
        )
        fsm.act("CHECKSUM",
            NextValue(tx_length, Mux(tx_payload, TCP_HEADER_LENGTH + len(response), TCP_HEADER_LENGTH)),
            Case(checksum_count, {i: NextValue(checksum, checksum + w) for i, w in enumerate(checksum_words)}),
            NextValue(checksum_count, checksum_count + 1),
            If(checksum_count == (len(checksum_words) - 1),
                NextState("CHECKSUM-FOLD0")
            )
        )
        fsm.act("CHECKSUM-FOLD0",
            NextValue(checksum, checksum[:16] + checksum[16:]),
            NextState("CHECKSUM-FOLD1")
        )
        fsm.act("CHECKSUM-FOLD1",
            NextValue(checksum, checksum[:16] + checksum[16:]),
            NextState("CHECKSUM-INVERT")
        )
        fsm.act("CHECKSUM-INVERT",
            NextValue(tx_checksum, ~checksum[:16]),
            NextValue(tx_count, 0),
            NextState("SEND")
        )
        fsm.act("SEND",
            tx.valid.eq(1),
            tx.last.eq(tx_count == (tx_length - 1)),
            tx.be.eq(1),
            tx.protocol.eq(TCP_PROTOCOL),
            tx.ip_address.eq(rx_remote_ip),
            tx.length.eq(tx_length),
            If(tx_count < TCP_HEADER_LENGTH,
                tx.data.eq(tx_header)
            ).Else(
                tx.data.eq(port_rd.dat_r)
            ),
            If(tx.ready,
                NextValue(tx_count, tx_count + 1),
                If(tx.last,
                    NextState("RECEIVE")
                )
            )
        )
