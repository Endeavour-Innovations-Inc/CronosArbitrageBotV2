import os
import json
import requests
from web3 import Web3
from datetime import datetime
from dotenv import load_dotenv
from decimal import Decimal
import time

# Import functions from library.py
from library import (
    fetch_token_price_from_coingecko,
    load_contract_abi,
    get_token_prices,
    calculate_imbalance_percent,
    calculate_imbalance_percent_corgiai_usdc,
    is_lp_balanced,
    calculate_trade_amount_to_balance_lp,
)

# Declare global variables at the top of your script
balance = None
balance_in_usd = None

def get_lp_reserves(lp_address, lp_abi):
    lp_contract = web3.eth.contract(address=lp_address, abi=lp_abi)
    reserves = lp_contract.functions.getReserves().call()
    return reserves

def check_lp_balance_for_vvs_corgiai_experimental(lp_address_str):
    print("_____________________________________________________________")
    print(f'Checking balance for LP pair at address EXPERIMENTAL {lp_address_str}...')
    lp_address = Web3.to_checksum_address(lp_address_str)
    lp_abi = load_contract_abi('lp_contract_abi.json')  # Your function to load the ABI

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
        percentage_difference, reserve_token0_usd, reserve_token1_usd = calculate_imbalance_percent_corgiai_usdc(reserves, (token0_price, token1_price))

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
    
def execute_trade(dominant_token, target_token, amount_to_trade, private_key, web3_instance): # works!!!!
    # Initialize Web3
    web3 = web3_instance

    # Router contract address and ABI
    router_address = '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae'  # Replace with actual address
    router_abi = load_contract_abi('RouterABI.json')  # Replace with actual ABI

    # Initialize contracts
    router_contract = web3.eth.contract(address=router_address, abi=router_abi)

    # Your wallet address
    # print(dir(web3.eth.account))
    my_account = web3.eth.account.from_key(private_key)
    my_address = my_account.address

    # Token contract addresses and ABIs for dominant and target tokens
    dominant_token_address = dominant_token  # Replace with actual address
    target_token_address = target_token  # Replace with actual address
    token_abi = load_contract_abi('VVS_abi.json')  # Replace with actual ABI for both tokens

    # Initialize token contracts
    dominant_token_contract = web3.eth.contract(address=dominant_token_address, abi=token_abi)
    target_token_contract = web3.eth.contract(address=target_token_address, abi=token_abi)

    # Build the transaction for token approval
    approve_txn = dominant_token_contract.functions.approve(
        router_address,
        amount_to_trade
    ).build_transaction({
        'chainId': 25,  # Cronos
        'gas': 159397,
        'gasPrice': web3.to_wei('4676', 'gwei'), # changed the amount of gas
        'nonce': web3.eth.get_transaction_count(my_address),
    })

    # Sign the transaction
    signed_approve_txn = web3.eth.account.sign_transaction(approve_txn, private_key)

    # Send the transaction and wait for it to be mined
    approval_tx_hash = web3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
    web3.eth.wait_for_transaction_receipt(approval_tx_hash)

    # Build the swap transaction
    swap_txn = router_contract.functions.swapExactTokensForTokens(
        amount_to_trade,
        1,  # Minimum amount of target token to receive, set to a reasonable value
        [dominant_token_address, target_token_address],  # Path (dominant_token -> target_token)
        my_address,  # Recipient
        int(time.time()) + 1200  # Deadline
    ).build_transaction({
        'chainId': 25,
        'gas': 159397,
        'gasPrice': web3.to_wei('4676', 'gwei'), # changed the amount of gas
        'nonce': web3.eth.get_transaction_count(my_address),
    })

    # Sign the swap transaction
    signed_swap_txn = web3.eth.account.sign_transaction(swap_txn, private_key)

    # Send the swap transaction
    swap_tx_hash = web3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
    web3.eth.wait_for_transaction_receipt(swap_tx_hash)

# TODO: Main Arbitrage Function
def main_arbitrage():
     # TODO: Identify Arbitrage Opportunities
    # - We start with VVS in our wallet, therefore we need to check two lp pairs: VVS/USDC & VVS/CorgiAI
    lp1_result = check_lp_balance_for_vvs_corgiai_experimental('0xfc07bf38408e4326f99dec96ba94f1e28af68842') # VVS/CorgiAI
    lp2_result = check_lp_balance_for_vvs_corgiai_experimental('0x814920D1b8007207db6cB5a2dD92bF0b082BDBa1') # VVS/USDC

    # Compare the LPs
    most_profitable_lp = compare_lps(lp1_result, lp2_result)

    # Check which LP is most profitable and execute trade accordingly
    if most_profitable_lp == lp1_result:
        print(f"Executing trade for LP1 with {lp1_result['token0_name']}/{lp1_result['token1_name']}")
        # Determine which token you have in your wallet and how much to trade
        if lp1_result['dominant_token'] == 'token0':
            amount_to_trade = lp1_result['amount_to_trade_token0']
        else:
            amount_to_trade = lp1_result['amount_to_trade_token1']
        
        # Execute the trade
        execute_trade(lp1_result['dominant_token'], amount_to_trade, other_parameters_here)
    else:
        print(f"Executing trade for LP2 with {lp2_result['token0_name']}/{lp2_result['token1_name']}")
        
        # Determine which token you have in your wallet and how much to trade
        if lp2_result['dominant_token'] == 'token0':
            amount_to_trade = lp2_result['amount_to_trade_token0']
        else:
            amount_to_trade = lp2_result['amount_to_trade_token1']
        
        # Execute the trade
        execute_trade(lp2_result['dominant_token'], amount_to_trade, other_parameters_here)

    # - Call the check_lp_balance_for_vvs_corgiai_experimental function
    # - Check if the LP is imbalanced and offers an arbitrage opportunity

    # TODO: Calculate Profit and Fees
    # - Use the output from check_lp_balance_for_vvs_corgiai_experimental
    # - Determine if the arbitrage is profitable after fees

    # TODO: Check for Slippage
    # - Ensure that the slippage is within an acceptable range

    # TODO: Execute Trades (If profitable and low slippage)
    # - Approve tokens for the Uniswap Router
    # - Build and send the swap transaction

    # TODO: Monitor and Log
    # - Print or log the result of the arbitrage
    # - Monitor the transaction until it's confirmed
    return

def calculate_gas_price():
    print("_____________________________________________________________")
    current_gas_price = web3.eth.gas_price
    print(f"Current gas price: {current_gas_price}")
    print("_____________________________________________________________")

def calculate_discount(lp_price, market_price):
    discount = ((lp_price - market_price) / market_price) * 100
    return discount

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

async def main():
    # while True:
        # time.sleep(20)  # Pauses the program for 5 seconds
        web3 = Web3(Web3.HTTPProvider(network_rpc))
        # VVS LP pairs
        #check_lp_balance_for_vvs_corgiai_experimental('0x019d9479606FBDd4aCB16488e0aAE49E4684322b') # WETH-CRO
        #check_lp_balance_for_vvs_corgiai_experimental('0x5383202D48C24aAA19873366168f2Ed558a00ff0') # WBTC-CRO -0.24
        #check_lp_balance_for_vvs_corgiai_experimental('0x0101112C7aDdb2E8197922e9cFa17cbAA935ECCc') #WETH-WBTC 
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('0x93fc0acf77edd68e611f8a776c9995f350f84274') # Mona - ETH
        #check_lp_balance_for_vvs_corgiai_experimental('0x0b75163715c5d26aec23461c0499ffa626fd3021') # ETH - Zora -does not even work
        #check_lp_balance_for_vvs_corgiai_experimental('0x2bbbf9dbf1e831fa3bce299b43415f54226da242') # Mona - Zora
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('0x67255a0ab5add6d65045e6e855842ca8b8a2b625') # WCRO-USDC
        #check_lp_balance_for_vvs_corgiai_experimental('0xc0961175f0cdd04110220c4effb74221055dd547') # WCRO-USDT
        #check_lp_balance_for_vvs_corgiai_experimental('0x0438a75009519f6284fa9e050e54d940302b2e93') # USDT-USDC
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('0x9d96706f31f520cb2404a3d2ad1a932b61a85acf') # VVS-WCRO
        #check_lp_balance_for_vvs_corgiai_experimental('0x3da5b8e5907acfbe8a08b1f00394c97e07476f2d') # VVS-USDC 1
        #check_lp_balance_for_vvs_corgiai_experimental('0x67255a0ab5add6d65045e6e855842ca8b8a2b625') # WCRO-USDC
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('0x8a513a09d9358e6ae46ff7c66b4d0e86769d04b4') # WCRO-WETH
        #check_lp_balance_for_vvs_corgiai_experimental('0x736e7df5efad1cac1a312725598befbb27f8bb08') # USDC-WETH
        #check_lp_balance_for_vvs_corgiai_experimental('0x67255a0ab5add6d65045e6e855842ca8b8a2b625') # WCRO-USDC
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('0x46d57ec4dc6a10d1a50a5f67accbff715ce81fda') # WBTC-WCRO
        #check_lp_balance_for_vvs_corgiai_experimental('0x736e7df5efad1cac1a312725598befbb27f8bb08') # WBTC-USDC
        #check_lp_balance_for_vvs_corgiai_experimental('0x67255a0ab5add6d65045e6e855842ca8b8a2b625') # WCRO-USDC
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('0x58bd242c1d2af2630318446ff3cf947925821de6') # CORGIAI-USDC
        #check_lp_balance_for_vvs_corgiai_experimental('0x686c7ac3f635c67670b50b87ddd52518554aed2a') # WCRO-CORGIAI
        #check_lp_balance_for_vvs_corgiai_experimental('0x67255a0ab5add6d65045e6e855842ca8b8a2b625') # WCRO-USDC
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('0x7901f798ab39a7b37e077fa7cfb473e591f134ca') # VVS-CORGIAI
        #check_lp_balance_for_vvs_corgiai_experimental('0x3da5b8e5907acfbe8a08b1f00394c97e07476f2d') # VVS-USDC 1
        #check_lp_balance_for_vvs_corgiai_experimental('0x58bd242c1d2af2630318446ff3cf947925821de6') # CORGIAI-USDC
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('0x08d819bf919f5d43880c9358c0648ad535880e64') # WCRO-TONIC
        #check_lp_balance_for_vvs_corgiai_experimental('0x2bb6ff4651a1f591995295c71ac2ac9f8b44a910') # VVS-TONIC
        #check_lp_balance_for_vvs_corgiai_experimental('0x9d96706f31f520cb2404a3d2ad1a932b61a85acf') # VVS-WCRO
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('0x9d96706f31f520cb2404a3d2ad1a932b61a85acf') # VVS-WCRO
        #check_lp_balance_for_vvs_corgiai_experimental('0x47526aeda324c8c942b24d3ce8f6763667c52016') # VVS-USDC 2
        #check_lp_balance_for_vvs_corgiai_experimental('0x67255a0ab5add6d65045e6e855842ca8b8a2b625') # WCRO-USDC
        print("_________________________________________________________________________________________________")
                
        #check_lp_balance_for_vvs_corgiai_experimental('0x7901f798ab39a7b37e077fa7cfb473e591f134ca') # VVS-CORGIAI
        #check_lp_balance_for_vvs_corgiai_experimental('0x47526aeda324c8c942b24d3ce8f6763667c52016') # VVS-USDC 2
        #check_lp_balance_for_vvs_corgiai_experimental('0x58bd242c1d2af2630318446ff3cf947925821de6') # CORGIAI-USDC
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
                
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
                
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        #check_lp_balance_for_vvs_corgiai_experimental('') # 
        print("_________________________________________________________________________________________________")
        


if __name__ == '__main__':
    load_dotenv()
    network_rpc = os.environ.get('NETWORK_RPC')

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