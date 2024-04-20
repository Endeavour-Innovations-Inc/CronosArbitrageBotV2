import json
from web3 import Web3
from utilities.config import NETWORK_RPC

# Initialize Web3 instance at the module level so it's accessible to all functions
web3 = Web3(Web3.HTTPProvider(NETWORK_RPC))

def load_contract_abi(file_name):
    with open(file_name, 'r') as file:
        return json.load(file)

def get_contract_instance(web3, address, abi_path):
    abi = load_contract_abi(abi_path)
    return web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)

def get_lp_reserves(lp_address, lp_abi):
    lp_contract = web3.eth.contract(address=lp_address, abi=lp_abi)
    reserves = lp_contract.functions.getReserves().call()
    return reserves

def get_token_details(contract):
    name = contract.functions.name().call()
    decimals = contract.functions.decimals().call()
    return name, decimals

def get_token_addresses(lp_contract):
    token0_address = lp_contract.functions.token0().call()
    token1_address = lp_contract.functions.token1().call()
    return token0_address, token1_address
