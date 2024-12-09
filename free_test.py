import struct
import time

time_stamp = time.time()

print("time_stamp: ", time_stamp)

header = struct.pack(">d", time_stamp)

print("header: ", header)
print("header length: ", len(header))
decode_header = struct.unpack(">d", header)[0]

print("decode_header: ", decode_header)
