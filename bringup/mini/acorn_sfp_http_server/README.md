[> Description
--------------
Gateware-only HTTP server over SFP (no CPU): LiteEth (MAC + ARP + IP + ICMP) with a tiny stateless
TCP/HTTP responder ([`http_server.py`](http_server.py)) serving [`index.html`](index.html) on port 80.

The TCP layer computes each reply from the received segment only:
- SYN -> SYN+ACK.
- Request (any segment with data) -> ACK+PSH+FIN with the full HTTP response.
- FIN -> ACK.

Limitations: the HTTP response (headers + page) must fit in a single TCP segment (1460 bytes), any
request returns the same page, other TCP ports are silently ignored (no RST).

[> Setup
--------
- Power from USB-C (J9).
- USB-C/JTAG connected to Host (J7).
- J10 to Acorn's JTAG connected through PICOEZMATE 6 cable.
- SFP 1000-Base-X <-> RJ45 module in SFP0 (or SFP1 with `--sfp=1`).
- Host configured on the 192.168.1.0/24 network (ex 192.168.1.100).

[> Build
--------
./sqrl_acorn.py --build --load

Use `--ip-address`, `--mac-address` and `--index` to change the IP/MAC addresses or the served page.

[> Check
--------
- ping 192.168.1.50 responding.
- curl http://192.168.1.50 (or http://192.168.1.50 in a web browser) showing the LiteX page.

[> Simulation
-------------
The design can also be simulated with Verilator and reached from the host through a tap0 interface
(requires root, Verilator, libevent, json-c and pythondata-misc-tapcfg):

- sudo ./sim.py
- curl http://192.168.1.50
