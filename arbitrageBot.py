import os
from web3 import Web3
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
    compare_lps,
    write_to_bookkeeping,
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
    hardcoded_usd_amount = balance_in_usd
    # hardcoded_usd_amount = 40

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

    discount_gain = 0
    swap_fee = 0
    gas_fee = 0

    # Custom logic for profit calculations based on the dominant token
    if dominant_token == 'token0':
        # Profit calculations for token1 (since token0 is dominant)
        toekn_name = token1_name
        discount_gain = Decimal(percentage_difference / 100) * Decimal(amount_to_trade_token1)
        swap_fee = Decimal(0.003) * Decimal(amount_to_trade_token1)
        gas_fee = Decimal(0.05) / Decimal(token1_price)
        dominant_token_address = token1_address
        target_token_address = token0_address
    elif dominant_token == 'token1':
        # Profit calculations for token0 (since token1 is dominant)
        toekn_name = token0_name
        discount_gain = Decimal(percentage_difference / 100) * Decimal(amount_to_trade_token0)
        swap_fee = Decimal(0.003) * Decimal(amount_to_trade_token0)
        gas_fee = Decimal(0.05) / Decimal(token0_price)
        dominant_token_address = token0_address
        target_token_address = token1_address

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
        'dominant_token_address': dominant_token_address,
        'target_token_address': target_token_address,
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
    
def execute_trade(dominant_token, target_token, amount_to_trade, private_key, web3_instance):
    # Initialize Web3
    web3 = web3_instance

    # Your wallet address
    my_account = web3.eth.account.from_key(private_key)
    my_address = my_account.address

    # Fetch the current nonce
    current_nonce = web3.eth.get_transaction_count(my_address)

    # Router contract address and ABI
    router_address = '0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae'
    router_abi = load_contract_abi('RouterABI.json')

    # Initialize contracts
    router_contract = web3.eth.contract(address=router_address, abi=router_abi)

    # Token contract addresses and ABIs for dominant and target tokens
    dominant_token_address = dominant_token
    target_token_address = target_token
    token_abi = load_contract_abi('VVS_abi.json')

    # Initialize token contracts
    dominant_token_contract = web3.eth.contract(address=dominant_token_address, abi=token_abi)
    target_token_contract = web3.eth.contract(address=target_token_address, abi=token_abi)

    # Build the transaction for token approval
    approve_txn = dominant_token_contract.functions.approve(
        router_address,
        amount_to_trade
    ).build_transaction({
        'chainId': 25,
        'gas': 159397,
        'gasPrice': web3.to_wei('4676', 'gwei'),
        'nonce': current_nonce,
    })

    # Sign the transaction
    signed_approve_txn = web3.eth.account.sign_transaction(approve_txn, private_key)

    # Send the transaction and wait for it to be mined
    approval_tx_hash = web3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
    web3.eth.wait_for_transaction_receipt(approval_tx_hash)

    # Increment the nonce for the next transaction
    current_nonce += 1

    # Build the swap transaction
    swap_txn = router_contract.functions.swapExactTokensForTokens(
        amount_to_trade,
        1,
        [dominant_token_address, target_token_address],
        my_address,
        int(time.time()) + 1200
    ).build_transaction({
        'chainId': 25,
        'gas': 159397,
        'gasPrice': web3.to_wei('4700', 'gwei'),
        'nonce': current_nonce,
    })

    # Sign the swap transaction
    signed_swap_txn = web3.eth.account.sign_transaction(swap_txn, private_key)

    # Send the swap transaction
    swap_tx_hash = web3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
    web3.eth.wait_for_transaction_receipt(swap_tx_hash)

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

def get_highest_balance_token(web3, private_key, token_data):

    # Check connection
    if not web3.is_connected():
        print("Not connected to the network")
        return None

    # Set up your account
    account = web3.eth.account.from_key(private_key)
    my_address = account.address

    highest_balance = 0
    highest_balance_token = None

    for token in token_data:
        # Create contract instance
        token_contract = web3.eth.contract(address=token['address'], abi=token['abi'])

        # Fetch balance
        balance_wei = token_contract.functions.balanceOf(my_address).call()
        balance = web3.from_wei(balance_wei, 'ether')

        print(f"Balance of {token['name']}: {balance} tokens")

        if balance > highest_balance:
            highest_balance = balance
            highest_balance_token = token['name']

    return highest_balance_token, highest_balance

def to_wei(amount, decimals):
    return int(amount * (10 ** decimals))

async def main():
    while True:  # Assuming you want to keep checking
        time.sleep(20)
        token_data = [
            {'name': 'VVS', 'address': '0x2D03bECE6747ADC00E1a131BBA1469C15fD11e03', 'abi': load_contract_abi('VVS_abi.json')},
            {'name': 'CRO', 'address': '0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23', 'abi': load_contract_abi('CRO_abi.json')},
            {'name': 'Tonic', 'address': '0xDD73dEa10ABC2Bff99c60882EC5b2B81Bb1Dc5B2', 'abi': load_contract_abi('Tonic_abi.json')}
        ]

        highest_balance_token, highest_balance = get_highest_balance_token(web3, private_key, token_data)
        print(f"The token with the highest balance is {highest_balance_token} with {highest_balance} tokens).")
        
        if highest_balance_token == 'Tonic':
            lp1_result = check_lp_balance_for_vvs_corgiai_experimental('0xA922530960A1F94828A7E132EC1BA95717ED1eab')  # VVS/Tonic
            lp2_result = check_lp_balance_for_vvs_corgiai_experimental('0x4B377121d968Bf7a62D51B96523d59506e7c2BF0')  # CRO/Tonic
        elif highest_balance_token == 'VVS':
            lp1_result = check_lp_balance_for_vvs_corgiai_experimental('0xA922530960A1F94828A7E132EC1BA95717ED1eab')  # VVS/Tonic
            lp2_result = check_lp_balance_for_vvs_corgiai_experimental('0xbf62c67eA509E86F07c8c69d0286C0636C50270b')  # VVS/Cro
        elif highest_balance_token == 'CRO':
            lp1_result = check_lp_balance_for_vvs_corgiai_experimental('0x4B377121d968Bf7a62D51B96523d59506e7c2BF0')  # CRO/Tonic
            lp2_result = check_lp_balance_for_vvs_corgiai_experimental('0xbf62c67eA509E86F07c8c69d0286C0636C50270b')  # VVS/Cro
        
         # Compare LPs and find the most profitable one
        most_profitable_lp = compare_lps(lp1_result, lp2_result)  # Assuming you have a function to compare LPs

        # Check if the trade is profitable enough to execute
        if most_profitable_lp['net_profit_usd'] > 0.00 and most_profitable_lp['percentage_difference'] >= 0.4:
            # Extract dominant and target tokens from the most profitable LP
            dominant_token = most_profitable_lp['dominant_token']
            dominant_token_address = most_profitable_lp['dominant_token_address']
            target_token = most_profitable_lp['token0_name'] if dominant_token == most_profitable_lp['token1_name'] else most_profitable_lp['token1_name']
            target_token_address = most_profitable_lp['target_token_address'] 

            # Calculate the amount to trade based on the dominant token
            amount_to_trade = most_profitable_lp['amount_to_trade_token1'] if dominant_token == most_profitable_lp['token0_name'] else most_profitable_lp['amount_to_trade_token0']

            # Execute the trade
            print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            print(f"Dominant Token: {dominant_token})")
            print(f"Dominant Token Address: {dominant_token_address})")
            print(f"Target Token: {target_token})")
            print(f"Target Token Address: {target_token_address})")
            print(f"Amount to Trade: {amount_to_trade})")
            print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            execute_trade(dominant_token_address, target_token_address, to_wei(amount_to_trade, 18), private_key, web3)

            # Log the profit details
            write_to_bookkeeping(dominant_token, most_profitable_lp['net_profit'], most_profitable_lp['net_profit_usd'])

            # Resetting the variables to None
            dominant_token = None
            dominant_token_address = None
            target_token = None
            target_token_address = None
        else:
            print("Trade not profitable enough to execute.")

if __name__ == '__main__':
    load_dotenv()
    network_rpc = os.environ.get('NETWORK_RPC')
    private_key = os.environ.get('PRIVATE_KEY')

    # Token contract details (Replace these with the actual ABI and address)
    token_contract_abi = load_contract_abi('VVS_abi.json')
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
# Step 5: Wallet connection established with retrieving the amount of tokens in the wallet.
# Step 6: Balance Retrieved of VVS token
# Step 7: VVS Router Trade executed & gas optimized (5 cents)
# Step 8: Able to retrieve the token with the highest amount