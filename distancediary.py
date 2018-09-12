import boto3, json, math, decimal

# boto3 initializations. (missing keys for obvious reasons)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('')

help_response = "To use Distance diary, say something like: \"Alexa, tell Distance Diary I am going to drive\
ten miles.\" or \"Alexa, ask Distance Diary how many calories I have burned.\" What would you like to do?"
                 
welcome = "Welcome to Distance Diary! To use this skill, say something like: \"I'm going to drive three miles.\" \
or: \"Ask distance diary about my carbon footprint.\"."

# Constants
km_to_m_const = 0.62137
secs_per_min = 60
cents_per_dol = 100

avg_bike_mph = 10
avg_bike_calories_mile = 47

avg_car_price_mile = 0.608
avg_co2_emissions_mile = 0.404

# Error Messages

request_error = "When requesting statistics about a distance, be sure to say a proper distance, such as \
\"ten miles\"."
inform_error = "When telling me about a recent ride, be sure to say a proper distance, such as \
\"ten miles\"."
calculate_error = "When asking how to save a certain amount of money, be sure to include a valid distance, \
such as \"ten miles\"."



# Response json template.
def text_response(response, session_end=True):
    return {
                'version': '1.0',
                'response': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': response
                    },
                    'shouldEndSession': session_end
                }
            }
            
            
# Confirms user input.
def approval_response(response, verb, distance, session_end=False):
    return {
                'version': '1.0',
                'response': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': response
                    },
                    'shouldEndSession': session_end,
                    'directives': [
                        {
                            'type': 'Dialog.ConfirmIntent',
                            'updatedIntent': {
                                'name': 'request',
                                'confirmationStatus': 'NONE',
                                'slots': {
                                    'future_verb': {
                                        'name': 'future_verb',
                                        'value': verb,
                                        'confirmationStatus': 'CONFIRMED'
                                    },
                                    'distance': {
                                        'name': 'distance',
                                        'value': distance,
                                        'confirmationStatus': 'CONFIRMED'
                                    }
                                }
                            }
                        }
                    ]
                }
            }

    
# Gets miles from DynamoDB.
def get_miles_traveled(response):
    return response['Item']['miles_traveled']


# Gets calories from DynamoDB.
def get_calories_burned(response):
    return response['Item']['calories_burned']


# Gets money from DynamoDB.
def get_money_saved(response):
    return response['Item']['money_saved']
    
    
# Gets CO2 emissions from DynamoDB.
def get_co2_emissions(response):
    return response['Item']['co2_emissions']


# Updates the user's statistics.
def update_db(user_id, dist_results):
    response = table.get_item(
        Key={'user_id': user_id}
    )
    
    calories = decimal.Decimal(dist_results[0]) + get_calories_burned(response)
    co2 = decimal.Decimal(dist_results[1]) + get_co2_emissions(response)
    miles = decimal.Decimal(dist_results[2]) + get_miles_traveled(response)
    money = decimal.Decimal(dist_results[3]) + get_money_saved(response)

    table.update_item(
        Key={'user_id': user_id},
        AttributeUpdates={
            'calories_burned': {
                'Value': calories
            },
            'co2_emissions': {
                'Value': co2.quantize(decimal.Decimal('0.000'))
            },
            'miles_traveled': {
                'Value': miles
            },
            'money_saved': {
                'Value': money.quantize(decimal.Decimal('0.00'))
            }
        }
    )
    
# Resets a user's stats. 
def reset_stats(user_id):
    table.update_item(
        Key={'user_id': user_id},
        AttributeUpdates={
            'calories_burned': {
                'Value': 0
            },
            'co2_emissions': {
                'Value': 0
            },
            'miles_traveled': {
                'Value': 0
            },
            'money_saved': {
                'Value': 0
            }
        }
    )


# Converts dollars to dollars and cents.
def convert_dollars(money):
    dollars = int(math.floor(money))
    cents = int((money - dollars) * cents_per_dol)
    return dollars, cents

    
# Gets values from DynamoDB.
def get_info(intent, user_id):
    response = table.get_item(
        Key={'user_id': user_id}
    )

    distance_output = "You have gone {} miles without using your car."
    calories_output = "You have burned {} calories with your activities."
    savings_output = "You have saved {} dollars and {} cents travelling using sustainable means."
    co2_emissions = "You have lowered your carbon footprint by {} kilograms of CO2."
    full_output = "You have gone {} miles without using your car, burned {} calories, saved {} dollars and {} cents, \
and you have prevented {} kilograms of CO2 from entering the environment."
    
    if intent == 'return_distance':
        return distance_output.format(get_miles_traveled(response))
    elif intent == 'return_calories':
        return calories_output.format(get_calories_burned(response))
    elif intent == 'return_savings':
        dollars, cents = convert_dollars(get_money_saved(response))
        return savings_output.format(dollars, cents)
    elif intent == 'return_co':
        return co2_emissions.format(get_co2_emissions(response))
    elif intent == 'all':
        dist = get_miles_traveled(response)
        calories = get_calories_burned(response)
        money = get_money_saved(response)
        dollars, cents = convert_dollars(money)
        co2 = get_co2_emissions(response)
        return full_output.format(dist, calories, dollars, cents, co2)
    else:
        return 'Error, intent not found.'   


# Calculates money saved by riding.
def calculate_money_saved(distance):
    money_saved = distance * avg_car_price_mile
    dollars_saved = int(math.floor(money_saved))
    cents_saved = int((money_saved - dollars_saved) * cents_per_dol)
    return money_saved, dollars_saved, cents_saved
    
    
# Calculates time spent riding.
def calculate_biking(distance):
    bike_time = distance / avg_bike_mph
    bike_hours = int(math.floor((bike_time)))
    bike_minutes = int((bike_time - bike_hours) * secs_per_min)
    return bike_hours, bike_minutes


# Used to get values for calculating, checks whether the user is asking about
# the distance, or if they have already biked that distance.
def distance_query(event, user_id, query, confirmed=False):
    if query:
        distance = int(event['request']['intent']['slots']['distance']['value'])
        verb = event['request']['intent']['slots']['future_verb']['value']
    else:
        distance = int(event['request']['intent']['slots']['distance_']['value'])
    
    calories = distance * avg_bike_calories_mile
    co2_emissions = round(distance * avg_co2_emissions_mile, 2)
    money_saved, dollars_saved, cents_saved = calculate_money_saved(distance)
    bike_hours, bike_minutes = calculate_biking(distance)

    if confirmed:
        return [calories, co2_emissions, distance, money_saved]
    
    units = "miles"
    calories_plural = 's'
    dollars_plural = 's'
    cents_plural = 's'
    hours_plural = 's'
    mins_plural = 's'
    
    if distance == 1:
        units = "mile"
    if calories == 1:
        calories_plural = ''
    if dollars_saved == 1:
        dollars_plural = ''
    if cents_saved == 1:
        cents_plural = ''
    if bike_hours == 1:
        hours_plural = ''
    if bike_minutes == 1:
        mins_plural = ''
        
    if query:
        facts = "If you ride your bike {} {} you could burn {} calorie{}, save {} dollar{} and {} cent{}, \
and be there in {} hour{} and {} minute{}. You will also lower your carbon footprint by {} kilograms of CO2. \
Would you like to ride your bike there instead of driving?"
        return facts.format(distance, units, calories, calories_plural, dollars_saved, dollars_plural, cents_saved, 
                            cents_plural, bike_hours, hours_plural, bike_minutes, mins_plural, co2_emissions), \
                            verb, distance
    else:
        facts = "You rode {} {}, so you burned {} calorie{}, saved {} dollar{} and {} cent{}, and prevented {} kilograms of \
CO2 from entering the atmosphere. I will add that to your statistics."
        return facts.format(distance, units, calories, calories_plural, dollars_saved, dollars_plural, cents_saved,
                            cents_plural, co2_emissions)


# Tells user number of miles to ride to save a certain amount of money.
def calculate_goal(event):
    try:
        goal = int(event['request']['intent']['slots']['amount']['value'])
    except:
        return calculate_error
    required_miles = round(goal / avg_car_price_mile, 1)
    output = "If you want to save {} dollars, you will need to ride {} miles on a bike."
    return output.format(goal, required_miles)


# Adds new users to DynamoDB.
def dyna(x):
    response = table.get_item(
        Key={'user_id': x}
    )
    
    try:
        # Checks to see if a request to the database returns data.
        in_table = response['Item']
    except KeyError:
        # In the event that a userId is missing, it is added.
        table.put_item(
            Item={
                'user_id': x,
                'miles_traveled': 0,
                'calories_burned': 0,
                'money_saved': 0,
                'co2_emissions': 0
            }
        )


# Default handler.
def lambda_handler(event, context):
    user_id = event['session']['user']['userId']
    dyna(user_id)
    
    event_type = event['request']['type']
    
    if event_type == 'LaunchRequest':
        return text_response(welcome, False)
    elif event_type == 'IntentRequest':
        return intent_handler(event, user_id)
    elif event_type == 'SessionEndedRequest':
        return text_response('Goodbye.')
        

# Custom handler.
def intent_handler(event, user_id):
    intent = event['request']['intent']['name']
    getter_methods = ['return_distance', 'return_calories', 'return_savings', 'return_co']
    
    # Custom intents.
    if intent == 'request':
        confirmed = event['request']['intent']['confirmationStatus']

        try:
            distance = int(event['request']['intent']['slots']['distance']['value'])
        except:
            return text_response(request_error)
        
        if confirmed == 'NONE':
            response, verb, distance = distance_query(event, user_id, True)
            return approval_response(response, verb, distance)
        elif confirmed == 'CONFIRMED':
            dist_results = distance_query(event, user_id, True, True)
            update_db(user_id, dist_results)
            return text_response("I will update your statistics.")
        elif confirmed == 'DENIED':
            return text_response("Okay, maybe another time.")
        else:
            return text_response("I'm sorry, something went wrong.")
            
    elif intent == 'inform':
        try:
            distance = int(event['request']['intent']['slots']['distance_']['value'])
        except:
            return text_response(inform_error)

        dist_results = distance_query(event, user_id, False, True)
        update_db(user_id, dist_results)
        return text_response(distance_query(event, user_id, False))
    elif intent in getter_methods:
        return text_response(get_info(intent, user_id))
    elif intent == 'full_stats':
        return text_response(get_info('all', user_id))
    elif intent == 'savings_goal':
        return text_response(calculate_goal(event))
    elif intent == 'reset_stats':
        reset_stats(user_id)
        return text_response("Your statistics have been reset.")
        
    # Amazon intents.
    elif intent == 'AMAZON.HelpIntent':
        return text_response(help_response, False)
    elif intent == 'AMAZON.StopIntent' or intent == 'AMAZON.CancelIntent':
        return text_response("Goodbye.")
    else:
        return text_response("I don't know that one, ask Distance Diary for help to get sample utterances.")
