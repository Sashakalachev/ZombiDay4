extends Node3D
## Предпросмотр анимаций и регдоллов (сцена tools/poses.tscn).
## Аргументы: --ragdoll — после 1.5 с все персонажи падают регдоллом.
const Humanoid = preload("res://scripts/humanoid.gd")
var items := []
var t := 0.0
var killed := false
var want_ragdoll := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--ragdoll":
			want_ragdoll = true
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.45, 0.6, 0.75)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.65, 0.65, 0.7)
	var we := WorldEnvironment.new(); we.environment = env; add_child(we)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-40, -30, 0); add_child(sun)
	var ground := StaticBody3D.new()
	ground.collision_layer = 1
	var gs := CollisionShape3D.new(); var bs := BoxShape3D.new(); bs.size = Vector3(60, 1, 20); gs.shape = bs; gs.position.y = -0.5
	ground.add_child(gs)
	var gm := MeshInstance3D.new(); var pm := PlaneMesh.new(); pm.size = Vector2(60, 20); gm.mesh = pm
	gm.material_override = Game.mat(Color(0.3, 0.5, 0.2)); ground.add_child(gm)
	add_child(ground)
	var cam := Camera3D.new(); cam.position = Vector3(0, 1.4, 8.5); cam.fov = 50; add_child(cam)
	# [подпись, состояние, тип, предмет, вид зомби]
	var setups := [
		["idle", {"move": 0.0}, "player", ""],
		["walk", {"move": 0.6}, "player", ""],
		["run", {"move": 1.5}, "player", ""],
		["crouch", {"move": 0.2, "crouch": 1.0}, "player", ""],
		["bat: замах", {"hold": "item", "swing": 0.3, "style": "bat"}, "player", "bat"],
		["bat: удар", {"hold": "item", "swing": 0.5, "style": "bat"}, "player", "bat"],
		["axe: замах", {"hold": "item", "swing": 0.3, "style": "axe"}, "player", "axe"],
		["axe: удар", {"hold": "item", "swing": 0.52, "style": "axe"}, "player", "axe"],
		["spray", {"hold": "item", "spray": 0.3}, "player", "repellent"],
		["pistol", {"hold": "gun"}, "player", "pistol"],
		["walker", {"move": 0.45, "kind": "walker"}, "zombie", ""],
		["runner", {"move": 1.5, "kind": "runner"}, "zombie", ""],
		["spore", {"move": 0.35, "kind": "spore"}, "zombie", ""],
		["zombie атака", {"move": 0.0, "swing": 0.5, "kind": "walker"}, "zombie", ""],
	]
	var i := 0
	for s in setups:
		var m: Node3D
		if s[2] == "player":
			m = Humanoid.create("player", Game.skin_color, Game.shirt_color, Game.pants_color, Game.face_image)
			if s[3] != "": Humanoid.set_held(m, s[3])
		else:
			m = Humanoid.create("zombie", Color(0.45, 0.6, 0.35), Color(0.4, 0.3, 0.25), Color(0.22, 0.24, 0.3), Game.zombie_face(3))
		m.position = Vector3(-13.0 + i * 2.0, 0, 0)
		m.rotation.y = -0.6
		add_child(m)
		var l := Label3D.new(); l.text = s[0]; l.position = Vector3(m.position.x, 2.3, 0); l.pixel_size = 0.0075; l.billboard = BaseMaterial3D.BILLBOARD_ENABLED; add_child(l)
		items.append([m, s[1], s[2]])
		i += 1


func _process(delta: float) -> void:
	t += delta
	if want_ragdoll and t > 1.2 and not killed:
		killed = true
		for it in items:
			var m: Node3D = it[0]
			Humanoid.make_ragdoll(m, self, Vector3(randf_range(-4, 4), 3.0, -9.0))
			m.visible = false
		return
	if killed:
		return
	for it in items:
		var st: Dictionary = it[1].duplicate()
		st["phase"] = t * 4.0 + 0.9
		st["t"] = t
		if it[2] == "player":
			Humanoid.animate_player(it[0], st)
		else:
			Humanoid.animate_zombie(it[0], st)
