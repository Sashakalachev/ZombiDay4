extends Node
## Автотест логики заражений/инвентаря: godot --headless --path . res://tools/selftest.tscn
const PlayerScript = preload("res://scripts/player.gd")
class FakeWorld extends Node:
	var remote_players := {}
	var deaths := []
	func req_drop(_i, _c, _p): pass
	func player_died(r, t, _p, _a = null, _b = null, _c = null): deaths.append([r, t])
	func get_interaction(_p): return {}
	func hit_zombie(_a, _b, _c): pass
	func hit_remote(_a, _b): pass
	func broadcast_shot(_a, _b): pass
	func infection_allowed(_id): return true

var fails := 0
func check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond: fails += 1

func _ready() -> void:
	var fw := FakeWorld.new()
	add_child(fw)
	var p = PlayerScript.new()
	p.world = fw
	add_child(p)
	await get_tree().process_frame
	check(p.inventory[0] == null and p.inventory[1] == null and p.inventory[2] == null, "старт: хотбар пуст")
	check(p.outfit["torso"] == "own_shirt" and p.outfit["legs"] == "own_pants", "старт: на игроке футболка и штаны")
	p.add_item("bat", 1); p.add_item("knife", 1); p.add_item("beans", 1)
	check(p.inventory[0] != null and p.inventory[0]["id"] == "bat", "бита (крупное) -> слот 1 (спина)")
	check(p.inventory[1] != null and p.inventory[1]["id"] == "knife", "нож (мелкое) -> слот 2 (пояс)")
	check(p.inventory[2] == null and p.count_item("beans") == 1, "еда уходит в карманы, не в хотбар")
	p.take_off("torso")
	check(p.outfit["torso"] == "" and p.count_item("own_shirt") == 1, "снятая футболка лежит в инвентаре")
	p.inventory[0] = null; p.inventory[1] = null
	p.consume_id("beans"); p.consume_id("own_shirt")
	p.add_item("beans", 3); p.add_item("beans", 4)
	check(p.count_item("beans") == 7, "стаки консервов суммируются (7)")
	# каждое заражение: экспозиция 100% -> инкубация -> симптомы -> исход
	for id in Game.INFECTIONS.keys():
		p.infections.clear()
		p.dead = false
		fw.deaths.clear()
		p.expose(id, 1.0)
		check(p.infections.has(id), "%s: заражение возникает" % id)
		var d: Dictionary = Game.INFECTIONS[id]
		var steps := int((d["incubation"] + d["duration"]) / 0.5) + 40
		var announced := false
		for i in steps:
			p._update_infections(0.5)
			if p.infections.has(id) and p.infections[id]["announced"]:
				announced = true
			if p.dead: break
		check(announced, "%s: появились симптомы" % id)
		check(p.dead and fw.deaths.size() == 1 and fw.deaths[0][1] == d["turns"], "%s: исход — %s" % [id, "обращение в зомби" if d["turns"] else "смерть"])
	# профилактика: сыворотка на инкубации
	p.dead = false; p.infections.clear()
	p.expose("saliva", 1.0)
	p.add_item("serum", 1)
	p._use_item_now(p.find_slot("serum"))
	check(not p.infections.has("saliva"), "сыворотка снимает укус на инкубации")
	# лечение симптомов антифунгальным
	p.infections["spores"] = {"t": 100.0, "progress": 60.0, "announced": true}
	p.add_item("antifungal", 1)
	p._use_item_now(p.find_slot("antifungal"))
	check(not p.infections.has("spores"), "противогрибковое лечит споры (60% -> здоров)")
	# антисептик: только рано
	p.infections["blow"] = {"t": 200.0, "progress": 30.0, "announced": true}
	p.add_item("antiseptic", 1)
	p._use_item_now(p.find_slot("antiseptic"))
	check(p.infections.has("blow"), "антисептик не помогает на поздней стадии")
	p.infections.clear()
	p.expose("blow", 1.0)
	p.add_item("antiseptic", 1)
	p._use_item_now(p.find_slot("antiseptic"))
	check(not p.infections.has("blow"), "антисептик на свежей ране предотвращает инфекцию")
	# противогаз защищает от спор
	p.dead = false; p.infections.clear(); p.mask_owned = true; p.mask_worn = true; p.filter_left = 100.0
	for i in 400:
		p.spore_timer = 0.3
		p._update_environment(0.1)
	check(not p.infections.has("spores") and p.filter_left < 100.0, "в противогазе споры не заражают, фильтр расходуется")
	p.filter_left = 0.0
	var got := false
	for i in 3000:
		p.spore_timer = 0.3
		p._update_environment(0.1)
		if p.infections.has("spores"): got = true; break
	check(got, "без фильтра споры заражают")
	# клещ
	p.infections.clear(); p.ticks.clear(); p.ticks.append(0.0)
	for i in 500: p._update_environment(0.1)
	check(p.infections.has("zoonotic"), "присосавшийся >40с клещ даёт зоонозное заражение")
	# оральное
	p.infections.clear(); p.add_item("bottle_dirty", 1)
	var inf_cnt := 0
	for i in 200:
		p.infections.clear()
		p.expose("oral", 0.65)
		if p.infections.has("oral"): inf_cnt += 1
	check(inf_cnt > 90 and inf_cnt < 170, "грязная вода заражает примерно в 65%% случаев (%d/200)" % inf_cnt)
	print("ИТОГО ПРОВАЛОВ: %d" % fails)
	get_tree().quit(fails)
