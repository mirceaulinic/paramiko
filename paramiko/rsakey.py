#!/usr/bin/python

# Copyright (C) 2003-2004 Robey Pointer <robey@lag.net>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distrubuted in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Foobar; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
L{RSAKey}
"""

import base64

from Crypto.PublicKey import RSA
from Crypto.Hash import SHA, MD5
from Crypto.Cipher import DES3

from common import *
from message import Message
from ber import BER, BERException
import util
from pkey import PKey
from ssh_exception import SSHException

class RSAKey (PKey):
    """
    Representation of an RSA key which can be used to sign and verify SSH2
    data.
    """

    def __init__(self, msg=None, data=''):
        self.valid = False
        if (msg is None) and (data is not None):
            msg = Message(data)
        if (msg is None) or (msg.get_string() != 'ssh-rsa'):
            return
        self.e = msg.get_mpint()
        self.n = msg.get_mpint()
        self.size = len(util.deflate_long(self.n, 0))
        self.valid = True

    def __str__(self):
        if not self.valid:
            return ''
        m = Message()
        m.add_string('ssh-rsa')
        m.add_mpint(self.e)
        m.add_mpint(self.n)
        return str(m)

    def __hash__(self):
        h = hash(self.get_name())
        h = h * 37 + hash(self.e)
        h = h * 37 + hash(self.n)
        return hash(h)

    def get_name(self):
        return 'ssh-rsa'

    def _pkcs1imify(self, data):
        """
        turn a 20-byte SHA1 hash into a blob of data as large as the key's N,
        using PKCS1's \"emsa-pkcs1-v1_5\" encoding.  totally bizarre.
        """
        SHA1_DIGESTINFO = '\x30\x21\x30\x09\x06\x05\x2b\x0e\x03\x02\x1a\x05\x00\x04\x14'
        filler = '\xff' * (self.size - len(SHA1_DIGESTINFO) - len(data) - 3)
        return '\x00\x01' + filler + '\x00' + SHA1_DIGESTINFO + data

    def sign_ssh_data(self, randpool, data):
        hash = SHA.new(data).digest()
        rsa = RSA.construct((long(self.n), long(self.e), long(self.d)))
        sig = util.deflate_long(rsa.sign(self._pkcs1imify(hash), '')[0], 0)
        m = Message()
        m.add_string('ssh-rsa')
        m.add_string(sig)
        return m

    def verify_ssh_sig(self, data, msg):
        if (not self.valid) or (msg.get_string() != 'ssh-rsa'):
            return False
        sig = util.inflate_long(msg.get_string(), 1)
        # verify the signature by SHA'ing the data and encrypting it using the
        # public key.  some wackiness ensues where we "pkcs1imify" the 20-byte
        # hash into a string as long as the RSA key.
        hash = util.inflate_long(self._pkcs1imify(SHA.new(data).digest()), 1)
        rsa = RSA.construct((long(self.n), long(self.e)))
        return rsa.verify(hash, (sig,))

    def read_private_key_file(self, filename, password=None):
        # private key file contains:
        # RSAPrivateKey = { version = 0, n, e, d, p, q, d mod p-1, d mod q-1, q**-1 mod p }
        self.valid = False
        data = self._read_private_key_file('RSA', filename, password)
        try:
            keylist = BER(data).decode()
        except BERException:
            raise SSHException('Unable to parse key file')
        if (type(keylist) is not list) or (len(keylist) < 4) or (keylist[0] != 0):
            raise SSHException('Not a valid RSA private key file (bad ber encoding)')
        self.n = keylist[1]
        self.e = keylist[2]
        self.d = keylist[3]
        # not really needed
        self.p = keylist[4]
        self.q = keylist[5]
        self.size = len(util.deflate_long(self.n, 0))
        self.valid = True

    def write_private_key_file(self, filename, password=None):
        if not self.valid:
            raise SSHException('Invalid key')
        keylist = [ 0, self.n, self.e, self.d, self.p, self.q,
                    self.d % (self.p - 1), self.d % (self.q - 1),
                    util.mod_inverse(self.q, self.p) ]
        try:
            b = BER()
            b.encode(keylist)
        except BERException:
            raise SSHException('Unable to create ber encoding of key')
        self._write_private_key_file('RSA', filename, str(b), password)

    def generate(bits, progress_func=None):
        rsa = RSA.generate(bits, randpool.get_bytes, progress_func)
        key = RSAKey()
        key.n = rsa.n
        key.e = rsa.e
        key.d = rsa.d
        key.p = rsa.p
        key.q = rsa.q
        key.valid = True
        return key
    generate = staticmethod(generate)
