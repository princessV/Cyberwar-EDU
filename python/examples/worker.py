from enum import Enum
from somewhere import GameStuff
from somewhere import Farm_Message

State = Enum('State', 'searching pathing farming returning')

# Initial State
last_hp = MAX_HP
current_state = State.searching

# Save the city location
_, units, _, _, _ = game_stuff.scan()
city_coor = get_city(units) # No idea how this works
farm_coor = None
while True:
	# Get our state and the state of things around us from scan
	terrains, units, pos, hp, inv = game_stuff.scan()
	if hp < last_hp:
		# If we were attacked run away
		current_state = State.returning

	# Check for messages from C&C
	messages = game_stuff.receive_messages()
	for message in messages:
		# If we got a message telling us to return go back to the city
		if message.type = "Return":
			currrent_state = State.returning
		# If we got a message about a farm set that as our current farm
		if message.type = "Farm Location":
			farm_coor = message.data

	# If we haven't found a farm look for one
	if current_state is State.searching:
		for tile in terrains:
			if tile.type = GameStuff.farm:
				farm_coor = tile.coor
				current_state = State.pathing
				# Tell C&C the location of the farm
				message = new Message(type="Farm Location", data=tile.coor)
				game_stuff.send_message(message)
				continue

	if current_state is State.pathing:
		if Path(farm_coor):
			continue
		current_state = State.farming

	if current_state is State.farming:
		# If we get here we know we're on the farm
		if inv.current < inv.max:
			game_stuff.farm()
		current_state = State.returning

	if current_state is State.returning:
		if Path(city_coor):
			continue
		current_state = State.pathing

	# Throw? - we should never get here

def Path(pos, target):
	# first move so we in line with it row-wise, then column-wise
	if pos.x < target.x:
		move(up)
		return True
	if pos.x > target.x:
		move(down)
		return True
	if pos.y > target.y:
		move(right)
		return True
	if pos.y < target.y:
		move(left)
		return True
	# If we've reached our target return False
	return False