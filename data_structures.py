#! /usr/bin/env/ python3
# coding:utf-8

from collections import deque
from copy import deepcopy
from z3 import And, Not, BitVecRef, BitVecNumRef, Concat, Extract, simplify
from utils import BitVec256, BitVecVal256, zero8bit, checkBitVecRef256
from exceptions import DevelopmentErorr
from collections import defaultdict

WORDBITSIZE = 256
WORDBYTESIZE = WORDBITSIZE // 8


class Stack:

    def __init__(self, block_number=0, stdata=None, num_stack_var=0):
        # blockNumber will be VM object's member
        self.__blockNumber = block_number
        self.__stackdata = deque() if stdata is None else stdata
        self.__numStackVar = num_stack_var
        self.__size = lambda: len(self.__stackdata)

    def duplicate(self, new_block_number:int):
        return Stack(new_block_number, deepcopy(self.__stackdata), self.__numStackVar)

    def generateStackVar(self) -> BitVecRef:
        self.__numStackVar += 1
        return BitVec256('stackVar{}-{}'.format(self.__blockNumber, self.__numStackVar))

    def push(self, w:BitVecRef):
        if self.__size() < 1023:
            self.__stackdata.append(checkBitVecRef256(w))
        else:
            # TODO stack limit reached 1024
            pass

    def pop(self) -> BitVecRef:
        if self.__size() >= 1:
            return checkBitVecRef256(self.__stackdata.pop())
        else:
            # generate a symbolic variable
            # TODO this may cause stack underflow
            return self.generateStackVar()

    def swapx(self, x:int):
        if x < 1 or 16 < x:
            raise DevelopmentErorr()

        if x + 1 > self.__size():
            for _ in range(x + 1 - self.__size()):
                self.__stackdata.appendleft(self.generateStackVar())

        a = self.__stackdata[self.__size() - 1]
        self.__stackdata[self.__size() - 1] = self.__stackdata[self.__size() - 1 - x]
        self.__stackdata[self.__size() - 1 - x] = a

    def dupx(self, x:int):
        if x < 1 or 16 < x:
            raise DevelopmentErorr()

        if x > self.__size():
            for _ in range(x - self.__size()):
                self.__stackdata.appendleft(self.generateStackVar())

        self.__stackdata.append(self.__stackdata[self.__size() - x])

    def show_data(self):
        for i in range(self.__size())[::-1]:
            print("{}:{}".format(i, self.__stackdata[i]))


class Memory:
    # big-endian
    def __init__(self, block_number=0, immediate_data=None, num_memory_var=0):
        # blockNumber will be VM object's member
        self.__blockNumber = block_number
        self.__immediate_data = [] if immediate_data is None else immediate_data
        self.__size = lambda: len(self.__immediate_data)
        self.__numMemoryVar = num_memory_var

    def duplicate(self, new_block_number:int):
        return Memory(new_block_number, deepcopy(self.__immediate_data), self.__numMemoryVar)

    def __generateMemoryVar(self):
        self.__numMemoryVar += 1
        return BitVec256('memoryVar{}-{}'.format(self.__blockNumber, self.__numMemoryVar))

    def mstore(self, offset: BitVecNumRef, value: BitVecRef):
        if type(offset) != BitVecNumRef:
            raise DevelopmentErorr('Does not support memory operations indexed by symbolic variables.')

        offset = checkBitVecRef256(offset).as_long()
        checkBitVecRef256(value)

        if offset + WORDBYTESIZE > self.__size():
            d = offset + WORDBYTESIZE - self.__size()
            self.__immediate_data.extend([zero8bit() for _ in range(d)])

        #  for dict
        #
        # for i in range(self.__size(), offset + WORDBYTESIZE):
        #     self.__memdata[str(i)] = zero8bit()
        #
        for i in range(WORDBYTESIZE):
            self.__immediate_data[offset + (WORDBYTESIZE - 1 - i)] = Extract(i * 8 + 7, i * 8, value)

    def mstore8(self, offset: BitVecNumRef, value:BitVecRef):
        if type(offset) != BitVecNumRef:
            raise DevelopmentErorr('Does not support memory operations indexed by symbolic variables.')

        offset = checkBitVecRef256(offset).as_long()
        checkBitVecRef256(value)

        if offset >= self.__size():
            d = offset - self.__size() + 1
            self.__immediate_data.extend([zero8bit() for _ in range(d)])

        self.__immediate_data[offset] = simplify(Extract(7, 0, value))

    def mload(self, offset: BitVecNumRef):
        if type(checkBitVecRef256(offset)) is not BitVecNumRef:
            raise DevelopmentErorr('Does not support memory operations indexed by symbolic variables.')

        offset = checkBitVecRef256(offset).as_long()
        if offset + WORDBYTESIZE > self.__size():
            # ~ index out of bounds ~
            # generate a symblolic variable
            newmemvar = self.__generateMemoryVar()
            d = offset + WORDBYTESIZE - self.__size()
            if d < WORDBYTESIZE:
                for i in range(d):
                    self.__immediate_data.append(Extract((d - i - 1) * 8 + 7, (d - i - 1) * 8, newmemvar))
                return simplify(Concat(self.__immediate_data[offset: WORDBYTESIZE+offset]))
            else:
                self.mstore(BitVecVal256(offset), newmemvar)
                return newmemvar

        elif offset < 0:
            # TODO  index out of bounds
            pass
        else:
            return simplify(
                Concat(self.__immediate_data[offset: WORDBYTESIZE+offset]))

    def msize(self):
        return self.__size()

    def show_data(self):
        print(self.__immediate_data)


class Storage:
    def __init__(self, block_number=0, storage_data=None, num_storage_var=0):
        self.__block_number = block_number
        self.__storage_data = {} if storage_data is None else storage_data
        self.__num_storage_var = num_storage_var

    def __generate_storage_var(self):
        self.__num_storage_var += 1
        return BitVec256('storageVar{}-{}'.format(self.__block_number, self.__num_storage_var))

    def sload(self, key: BitVecRef) -> BitVecRef:
        key = str(checkBitVecRef256(key))
        if key in self.__storage_data.keys():
            return self.__storage_data[key]
        else:
            newvar = self.__generate_storage_var()
            self.__storage_data[key] = newvar
            return newvar

    def sstore(self, key: BitVecRef, value: BitVecRef):
        checkBitVecRef256(key)
        checkBitVecRef256(value)
        # # concrete value
        # if type(key) == BitVecNumRef:
        #     key = key.as_long()
        # # symbolic variable
        # else:
        #     key = str(key)
        self.__storage_data[str(key)] = value

    def duplicate(self, new_block_number):
        return Storage(new_block_number, deepcopy(self.__storage_data), self.__num_storage_var)

    def show_data(self):
        for k,v in self.__storage_data.items():
            print('key={}, value={}'.format(k, v))


# TODO return data
class Returndata():
    pass
# TODO call data
class Calldata:
    pass


class WorldState:
    def __init__(self):
        self.execution_environments = []
        self.block_hashes = {}
        self.accounts = {}

    def add_account(self, bytecode:str):
        # アカウント番号とAccount address生成
        new_num = len(self.accounts)
        new_addr = BitVec256('address{}'.format(new_num))

        # Account生成
        account = Account(bytecode,new_num)

        # アドレスとAccountインスタンスの対応をaccountsに保存
        self.accounts[new_addr] = account

        return new_addr

    def get_account_num(self, addr:BitVecRef) -> int:
        return self.accounts[addr].get_account_num()

    # def generate_execution_environment(self):
    #     pass
    '''
     IH= {
            'coinbase': BitVec('coinbase_{}'.format(eenum), 256),
            'timestamp': BitVec('timestamp_{}'.format(eenum), 256),
            'number': BitVec('blocknumber_{}'.format(eenum), 256),
            'difficulty': BitVec('difficulty_{}'.format(eenum), 256),
            'gaslimit': BitVec('_{}'.format(eenum), 256)
        }
    '''



class Execution_environment:
    def __init__(self, exec_env_num:int, Ia:BitVecRef, Io:BitVecRef, Ip:BitVecRef, Id:BitVecRef, Is:BitVecRef, Iv:BitVecRef, Ib:BitVecRef, IH:dict, Ie:int, Iw:bool):
        self.exec_env_num = exec_env_num
        self.this_address = Ia
        self.tx_originator = Io
        self.gasprice = Ip
        self.msg_data = Id
        self.msg_sender = Is
        self.msg_value = Iv
        self.this_code = Ib
        self.block_header = IH
        self.depth_of_call = Ie
        self.permission_to_change_state = Iw
        #self.accounts = []
    # about Iw: https://ethereum.stackexchange.com/questions/49210/execution-environment-variables-iw-and-ie
    # def add_account(self,code: str):
    #     self.accounts.append(Account())


    def show_all(self):
        print(self.exec_env_num,self.this_address,self.tx_originator,self.gasprice,
              self.msg_data,self.msg_sender,self.msg_value,self.this_code,self.block_header,
              self.depth_of_call,self.permission_to_change_state)


class Machine_state:
    def __init__(self,
        pc=0,
        memory=Memory(),
        stack=Stack(),
        storage=Storage(),
        #returndata=Returndata(),
        #calldata=Calldata()
        ):
        self.pc = pc
        self.memory = memory
        self.stack = stack
        self.storage = storage
        # self.returndata = returndata
        # self.calldata = calldata

    def duplicate(self, new_block_number):
        return Machine_state(
            self.__pc,
            self.__memory.duplicate(new_block_number),
            self.__stack.duplicate(new_block_number),
            self.__storage.duplicate(new_block_number)
        )

    def get_pc(self):
        return self.__pc

    def set_pc(self, pc:int):
        self.__pc = pc

    def get_memory(self):
        return self.__memory

    def get_stack(self):
        return self.__stack

    def get_storage(self):
        return self.__storage

# for type annotation in methods of BasicBlock
class BasicBlock:
    pass

class BasicBlock:
    def __init__(self,
                 account_number : int,
                 block_number: int,
                 machine_state: Machine_state=None,
                 storage: Storage=None,
                 mnemonics: list = None,
                 path_condition=True,
                 cond_exp_for_JUMP=False,
                 dfs_stack=None,
                 call_stack=None):

        self.__account_number = account_number
        self.__block_number = block_number
        self.__machine_state = Machine_state() if machine_state is None else machine_state
        self.__storage = Storage() if storage is None else storage
        self.__mnemonics = [] if mnemonics is None else mnemonics
        self.__path_condition = path_condition
        self.__cond_exp_for_JUMP = cond_exp_for_JUMP
        self.dfs_stack = [] if dfs_stack is None else dfs_stack
        self.call_stack = [] if call_stack is None else call_stack

    def add_mnemonic(self, numaddedbyte: int, mnemonic: str):

        self.__mnemonics.append((self.__machine_state.get_pc(), mnemonic))
        self.__machine_state.set_pc(self.__machine_state.get_pc() + numaddedbyte)

    def get_mnemonic(self):
        return self.__mnemonics

    def duplicate(self, account_number:int, new_block_number:int):
        return BasicBlock(account_number, new_block_number,
                          self.__machine_state.duplicate(new_block_number),
                          self.__storage.duplicate(new_block_number),
                          deepcopy(self.__mnemonics),
                          deepcopy(self.__path_condition),
                          deepcopy(self.__cond_exp_for_JUMP),
                          deepcopy(self.dfs_stack),
                          deepcopy(self.call_stack)
                          )

    def push_dfs_stack(self, block:BasicBlock):
        self.dfs_stack.append(block)

    def pop_dfs_stack(self):
        self.dfs_stack.pop()

    def show_dfs_stack(self):
        print(self.dfs_stack)

    def push_call_stack(self, block:BasicBlock):
        self.call_stack.append(block)

    def pop_call_stack(self):
        self.call_stack.pop()

    def show_call_stack(self):
        print(self.call_stack)

    def set_pc(self, pc):
        self.__machine_state.set_pc(pc)

    # TODO
    # VMが持つデータを取り出す(pc以外は参照として)
    def extract_data(self):
        return self.__machine_state.get_memory(),\
               self.__machine_state.get_stack(),\
               self.__storage,\
               self.__machine_state.get_pc()

    def add_constraint_to_path_condition(self, constraint):
        self.__path_condition = simplify(And(self.__path_condition, constraint))

    def get_path_condition(self):
        return self.__path_condition

    def set_cond_exp_for_JUMP(self, constraint):
        self.__cond_exp_for_JUMP = constraint

    def get_cond_exp_for_JUMP(self):
        return self.__cond_exp_for_JUMP

class CfgManager:
    def __init__(self, cfg_num:int):
        self.cfg_num = cfg_num
        self.__basic_blocks = []
        self.__visited_blocks = []
        self.__edges = defaultdict(list)
        self.__CFG_name = "CFG_{}".format(self.cfg_num)

    def add_basic_block(self, basic_block : BasicBlock):
        self.__basic_blocks.append(basic_block)

    def add_visited_block(self, basic_block : BasicBlock):
        self.__visited_blocks.append(basic_block)

    def get_basic_blocks(self):
        return self.__basic_blocks

    def get_visited_blocks(self):
        return self.__visited_blocks

    def add_edge(self, origin: BasicBlock, dest: BasicBlock):
        self.__edges[origin].append(dest)

    def get_dest_block(self, origin: BasicBlock):
        return self.__edges[origin]

    def get_CFG_name(self):
        return self.__CFG_name


class Account:
    def __init__(self, bytecode: str, account_num: int, balance:BitVecRef = None):
        self.bytecode = bytecode
        self.codesize = lambda:len(bytecode)
        self.account_num = account_num
        self.balance = BitVec256('account_balance_{}'.format(self.account_num)) if balance is None else balance

    def get_account_num(self) -> int:
        return self.account_num







# if __name__ == '__main__':
#     m = Memory()
#     m.mstore(0,BitVec("hoge",256))
#     print(m.mload(0))
#     print(m.mload(45))
#     print(m.__memdata)
#
#     s = Stack()
#     t = BitVecVal(100+ 2**1024-1,256)
#     print(t)
#     s.push(t)
#     print(s.pop())
#     print(s.pop())
#     s.push(BitVecVal(1,256))
#     s.push(BitVecVal(2,256))
#     s.push(BitVec("hoge",256))
#     s.push(BitVecVal(4,256))
#     s.swapx(1)
#     s.dupx(1)
#     s.dupx(5)
#     s.swapx(4)
#     import sys
#     for i in range(s.size()):
#         sys.stdout.write(str(s.__stackdata[i]))
#         sys.stdout.write(' ')
#
#     s2 = s.duplicate(1)
#     for i in range(s2.size()):
#         sys.stdout.write('i={} '.format(i))
#         sys.stdout.write(str(simplify(s2.__stackdata[i] * BitVecVal(2, 256) / BitVecVal(2, 256))))
#         print()
#
#
#
