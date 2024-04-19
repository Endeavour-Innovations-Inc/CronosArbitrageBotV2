import os
from web3 import Web3
from dotenv import load_dotenv
from decimal import Decimal
import sys
import time
from datetime import datetime

# Import functions from library.py
from library import (
    fetch_token_price_from_coingecko,
    load_contract_abi,
    get_token_prices,
    calculate_imbalance_percent,
    calculate_imbalance_percent_uint_6_18,
    calculate_imbalance_percent_uint_18_6,
    calculate_imbalance_percent_uint_6_6,
    is_lp_balanced,
    calculate_trade_amount_to_balance_lp,
    get_lp_reserves,
)

# Declare global variables at the top of your script
balance = None
balance_in_usd = None

def get_lp_reserves(lp_address, lp_abi):
    lp_contract = web3.eth.contract(address=lp_address, abi=lp_abi)
    reserves = lp_contract.functions.getReserves().call()
    return reserves

def uint18LPbalance(lp_address_str):
    print("_____________________________________________________________")
    print(f'Checking balance for LP pair at address EXPERIMENTAL {lp_address_str}...')
    lp_address = Web3.to_checksum_address(lp_address_str)
    lp_abi = load_contract_abi('ABIs/lp_contract_abi.json')  # Your function to load the ABI

    # Create a contract object using the same method you used in get_lp_reserves
    lp_contract = web3.eth.contract(address=lp_address, abi=lp_abi)

    # Retrieve token addresses from the contract
    token0_address = lp_contract.functions.token0().call()
    token1_address = lp_contract.functions.token1().call()

    reserves = get_lp_reserves(lp_address, lp_abi)
    token0_price, token1_price = get_token_prices(token0_address, token1_address)  # Unpack the prices here

    ### Naming
    # Create contract objects for the tokens using the same ABI
    token0_contract = web3.eth.contract(address=token0_address, abi=lp_abi)
    token1_contract = web3.eth.contract(address=token1_address, abi=lp_abi)

    # Retrieve and print the names of the tokens
    # Retrieve and print the names and decimals of the tokens
    token0_name = token0_contract.functions.name().call()
    token0_decimals = token0_contract.functions.decimals().call()
    token1_name = token1_contract.functions.name().call()
    token1_decimals = token1_contract.functions.decimals().call()
    print(f"Token 0: {token0_name} ({token0_address}), Decimals: {token0_decimals}")
    print(f"Token 1: {token1_name} ({token1_address}), Decimals: {token1_decimals}")

    # Choose the appropriate function based on the number of decimals
    if token0_decimals == 18 and token1_decimals == 18:
        percentage_difference, reserve_token0_usd, reserve_token1_usd = calculate_imbalance_percent(reserves, (token0_price, token1_price))
    elif token0_decimals == 18 and token1_decimals == 6:
        percentage_difference, reserve_token0_usd, reserve_token1_usd = calculate_imbalance_percent_uint_18_6(reserves, (token0_price, token1_price))
    elif token0_decimals == 6 and token1_decimals == 18:
        percentage_difference, reserve_token0_usd, reserve_token1_usd = calculate_imbalance_percent_uint_6_18(reserves, (token0_price, token1_price))
    elif token0_decimals == 6 and token1_decimals == 6:
        percentage_difference, reserve_token0_usd, reserve_token1_usd = calculate_imbalance_percent_uint_6_6(reserves, (token0_price, token1_price))                                                                                     
    else:
        print()

    print(f"Percentage difference between reserves: {percentage_difference:.2f}%")
    print(f"USD value of {token0_name} reserves: ${reserve_token0_usd:.2f}")
    print(f"USD value of {token1_name} reserves: ${reserve_token1_usd:.2f}")

    dominant_token = None  # Initialize variable to store the dominant token

    if is_lp_balanced(percentage_difference):
        print("The LP is balanced.")
    else:
        print("The LP is imbalanced.")
        if reserve_token0_usd > reserve_token1_usd:
            print(f"{token0_name} has a higher USD value in reserves.")
            dominant_token = 'token0'
        else:
            print(f"{token1_name} has a higher USD value in reserves.")
            dominant_token = 'token1'

    amount_to_trade_token0_lq, amount_to_trade_token1_lq = calculate_trade_amount_to_balance_lp(reserve_token0_usd, reserve_token1_usd, token0_price, token1_price)

    # Hardcode the amount to trade in USD
    # hardcoded_usd_amount = balance_in_usd
    hardcoded_usd_amount = 100

    # Convert the amounts to trade into their dollar equivalent
    amount_to_trade_token0_usd = Decimal(amount_to_trade_token0_lq) * Decimal(token0_price)
    amount_to_trade_token1_usd = Decimal(amount_to_trade_token1_lq) * Decimal(token1_price)

    print(f"Total amount on discount of Token 0 ({token0_name}): {amount_to_trade_token0_lq} in USD: ${amount_to_trade_token0_usd:.2f}")
    print(f"Total amount on discount of Token 1 ({token1_name}): {amount_to_trade_token1_lq} in USD: ${amount_to_trade_token1_usd:.2f}")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

     # Convert the hardcoded USD amount to the respective token amounts
    amount_to_trade_token0 = Decimal(hardcoded_usd_amount) / Decimal(token0_price)
    amount_to_trade_token1 = Decimal(hardcoded_usd_amount) / Decimal(token1_price)

    print(f"Amount available in wallet to trade of Token 0 ({token0_name}): {amount_to_trade_token0} in USD: ${hardcoded_usd_amount}")
    print(f"Amount available in wallet to trade of Token 1 ({token1_name}): {amount_to_trade_token1} in USD: ${hardcoded_usd_amount}")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    toekn_name = None

    # Custom logic for profit calculations based on the dominant token
    if dominant_token == 'token0':
        # Profit calculations for token1 (since token0 is dominant)
        toekn_name = token1_name
        discount_gain = Decimal(percentage_difference / 100) * Decimal(amount_to_trade_token1)
        swap_fee = Decimal(0.003) * Decimal(amount_to_trade_token1)
        gas_fee = Decimal(0.05) / Decimal(token1_price)
    elif dominant_token == 'token1':
        # Profit calculations for token0 (since token1 is dominant)
        toekn_name = token0_name
        discount_gain = Decimal(percentage_difference / 100) * Decimal(amount_to_trade_token0)
        swap_fee = Decimal(0.003) * Decimal(amount_to_trade_token0)
        gas_fee = Decimal(0.05) / Decimal(token0_price)
    else:
        toekn_name = ''
        discount_gain = 0
        swap_fee = 0
        gas_fee = 0

    # Calculate Net Profit
    gross_gain = discount_gain
    total_fees = swap_fee + gas_fee
    net_profit = gross_gain - total_fees

    # Calculate USD equivalents
    if dominant_token == 'token0':
        discount_gain_usd = discount_gain * Decimal(token1_price)
        swap_fee_usd = swap_fee * Decimal(token1_price)
        gas_fee_usd = gas_fee * Decimal(token1_price)
        net_profit_usd = net_profit * Decimal(token1_price)
    elif dominant_token == 'token1':
        discount_gain_usd = discount_gain * Decimal(token0_price)
        swap_fee_usd = swap_fee * Decimal(token0_price)
        gas_fee_usd = gas_fee * Decimal(token0_price)
        net_profit_usd = net_profit * Decimal(token0_price)
    else:
        discount_gain_usd = 0
        swap_fee_usd = 0
        gas_fee_usd = 0
        net_profit_usd = 0

    print(f"Discount Gain on selling {toekn_name}: {discount_gain} (~${discount_gain_usd:.2f} USD)")
    print(f"Swap Fee on selling {toekn_name}: {swap_fee} (~${swap_fee_usd:.2f} USD)")
    print(f"Gas Fee in {toekn_name}: {gas_fee} (~${gas_fee_usd:.2f} USD)")
    print(f"Net Profit in {toekn_name}: {net_profit} (~${net_profit_usd:.2f} USD)")

    # Create a dictionary to store all the relevant information
    result = {
        'dominant_token': dominant_token,
        'token0_name': token0_name,
        'token1_name': token1_name,
        'percentage_difference': percentage_difference,
        'reserve_token0_usd': reserve_token0_usd,
        'reserve_token1_usd': reserve_token1_usd,
        'amount_to_trade_token0': amount_to_trade_token0,
        'amount_to_trade_token1': amount_to_trade_token1,
        'amount_to_trade_token0_usd': amount_to_trade_token0_usd,
        'amount_to_trade_token1_usd': amount_to_trade_token1_usd,
        'discount_gain': discount_gain,
        'swap_fee': swap_fee,
        'gas_fee': gas_fee,
        'net_profit': net_profit,
        'discount_gain_usd': discount_gain_usd,
        'swap_fee_usd': swap_fee_usd,
        'gas_fee_usd': gas_fee_usd,
        'net_profit_usd': net_profit_usd
    }

    print("_____________________________________________________________")
    return result

def compare_lps(lp1_result, lp2_result):
    if lp1_result['net_profit_usd'] > lp2_result['net_profit_usd']:
        print(f"LP1 with {lp1_result['token0_name']}/{lp1_result['token1_name']} is more profitable for arbitrage.")
        return lp1_result
    else:
        print(f"LP2 with {lp2_result['token0_name']}/{lp2_result['token1_name']} is more profitable for arbitrage.")
        return lp2_result

def get_token_balance(network_rpc, private_key, token_contract_abi, token_contract_address):
    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(network_rpc))

    # Check connection
    if not web3.is_connected():
        print("Not connected to the network")
        return None

    # Set up your account
    account = web3.eth.account.from_key(private_key)
    my_address = account.address

    # Create contract instance
    token_contract = web3.eth.contract(address=token_contract_address, abi=token_contract_abi)

    # Fetch balance
    balance_wei = token_contract.functions.balanceOf(my_address).call()
    balance = web3.from_wei(balance_wei, 'ether')

    return balance

def write_to_file(results, filename):
    with open(filename, "a") as file:
        for result in results:
            file.write(f"{result['dominant_token']}, {result['token0_name']}, {result['token1_name']}, {result['percentage_difference']}\n")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        file.write(f"____________________________________________________________________{timestamp}\n")

async def main():
    while True:
        time.sleep(180)  # Pauses the program for 5 seconds
        web3 = Web3(Web3.HTTPProvider(network_rpc))
        result1 = uint18LPbalance('0xA922530960A1F94828A7E132EC1BA95717ED1eab') # VVS/Tonic
        result2 = uint18LPbalance('0x4B377121d968Bf7a62D51B96523d59506e7c2BF0') # CRO/Tonic
        result3 = uint18LPbalance('0xbf62c67eA509E86F07c8c69d0286C0636C50270b') # VVS/Cro // very good pair for arbitrage, dominant token flips constantly

        write_to_file([result1, result2, result3], "tokenData/tectonic_data.txt")
        print("_________________________________________________________________________________________________")
        time.sleep(180)  # Pauses the program for 5 seconds
        result7 = uint18LPbalance('0xfc07bf38408e4326f99dec96ba94f1e28af68842') # VVS/CORGI
        result8 = uint18LPbalance('0x8f9baccf9a130a755520cbabb20543adb3006f14') # CRO/CORGI
        result9 = uint18LPbalance('0xbf62c67eA509E86F07c8c69d0286C0636C50270b') # VVS/Cro

        write_to_file([result7, result8, result9], "tokenData/corgi_data.txt")
        print("_________________________________________________________________________________________________")
        time.sleep(180)  # Pauses the program for 5 seconds
        result4 = uint18LPbalance('0x34d1856ED8BBc20FA7b29776ad273FD8b22967BE') # VVS/VENO
        result5 = uint18LPbalance('0x523ad524721957c31Ca53512A4E50d82F53c5cAe') # CRO/VENO
        result6 = uint18LPbalance('0xbf62c67eA509E86F07c8c69d0286C0636C50270b') # VVS/Cro

        write_to_file([result4, result5, result6], "tokenData/veno_data.txt")
        print("_________________________________________________________________________________________________")
        time.sleep(180)  # Pauses the program for 5 seconds
        result10 = uint18LPbalance('0x6ae624714f221964aff3AB8D8276a7ec142a759f') # VVS/FUL
        result11 = uint18LPbalance('0x9B5a553f3E081999f0a6A3d582fD7Dc49e12761B') # CRO/FUL
        result12 = uint18LPbalance('0xbf62c67eA509E86F07c8c69d0286C0636C50270b') # VVS/Cro

        write_to_file([result10, result11, result12], "tokenData/ful_data.txt")
        print("_________________________________________________________________________________________________")
        time.sleep(180)  # Pauses the program for 5 seconds
        result13 = uint18LPbalance('0xe61Db569E231B3f5530168Aa2C9D50246525b6d6') # CRO/USDC
        result14 = uint18LPbalance('0xA111C17f8B8303280d3EB01BBcd61000AA7F39F9') # CRO/ETH
        result15 = uint18LPbalance('0xfd0Cd0C651569D1e2e3c768AC0FFDAB3C8F4844f') # ETH/USDC

        write_to_file([result13, result14, result15], "tokenData/cro_usdc_eth_data.txt")
        print("_________________________________________________________________________________________________")
        time.sleep(180)  # Pauses the program for 5 seconds
        result16 = uint18LPbalance('0xe61Db569E231B3f5530168Aa2C9D50246525b6d6') # CRO/USDC
        result17 = uint18LPbalance('0xbf62c67eA509E86F07c8c69d0286C0636C50270b') # CRO/VVS
        result18 = uint18LPbalance('0x814920D1b8007207db6cB5a2dD92bF0b082BDBa1') # VVS/USDC

        write_to_file([result16, result17, result18], "tokenData/cro_usdc_VVS_data.txt")
        print("_________________________________________________________________________________________________")


if __name__ == '__main__':
    load_dotenv()
    network_rpc = os.environ.get('NETWORK_RPC')
    private_key = os.environ.get('PRIVATE_KEY')

    # Token contract details (Replace these with the actual ABI and address)
    token_contract_abi = load_contract_abi('ABIs/VVS_abi.json')
    token_contract_address = "0x2D03bECE6747ADC00E1a131BBA1469C15fD11e03"  # VVS

    # Get token balance
    balance = get_token_balance(network_rpc, private_key, token_contract_abi, token_contract_address)

    if balance is not None:
        token_price_in_usd = fetch_token_price_from_coingecko(token_contract_address)
        balance_in_usd = balance * Decimal(token_price_in_usd)
        print(f"Your token balance is: {balance} tokens (~${balance_in_usd:.2f} USD)")

    web3 = Web3(Web3.HTTPProvider(network_rpc))

    if web3.is_connected():
        print('Connected to Cronos')
    else:
        print('Something went wrong')

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass


# Step 1: Connection to cronos successfull
# Step 2: Real time price fetched
# Step 3: Percent of imbalance calculations
# Step 4: All data & analytics retrieved
# Step 5: Wallet connection established with retrieving the amount of tokens in the wallet
# Step 6: Balance Retrieved of VVS token
# Step 7: VVS Router Trade executed & gas optimized (5 cents)