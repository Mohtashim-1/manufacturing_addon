frappe.provide("manufacturing_addon.container_3d");

manufacturing_addon.container_3d = {
	_loaded: false,

	load() {
		if (this._loaded && window.THREE && THREE.OrbitControls) {
			return Promise.resolve();
		}
		return new Promise((resolve) => {
			frappe.require("https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js", () => {
				frappe.require(
					"https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js",
					() => {
						this._loaded = true;
						resolve();
					}
				);
			});
		});
	},

	destroy(viewer) {
		if (!viewer) return;
		if (viewer.animationId) cancelAnimationFrame(viewer.animationId);
		if (viewer.resizeHandler) window.removeEventListener("resize", viewer.resizeHandler);
		if (viewer.renderer) {
			viewer.renderer.dispose();
			if (viewer.renderer.domElement && viewer.renderer.domElement.parentNode) {
				viewer.renderer.domElement.parentNode.removeChild(viewer.renderer.domElement);
			}
		}
	},

	parse_dims_cm(text) {
		const match = String(text || "").match(
			/(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)/
		);
		if (!match) return [45, 40, 35];
		return [parseFloat(match[1]), parseFloat(match[2]), parseFloat(match[3])];
	},

	item_color(so_item) {
		let hash = 0;
		const text = so_item || "item";
		for (let i = 0; i < text.length; i++) hash = text.charCodeAt(i) + ((hash << 5) - hash);
		const hue = (Math.abs(hash) % 360) / 360;
		return new THREE.Color().setHSL(hue, 0.48, 0.55);
	},

	add_carton_mesh(scene, x, y, z, dims, color, scale) {
		let w = dims[0] * scale;
		let h = dims[2] * scale;
		let d = dims[1] * scale;
		w = Math.max(0.12, Math.min(w, 0.48));
		d = Math.max(0.12, Math.min(d, 0.48));
		h = Math.max(0.12, Math.min(h, 0.55));

		const cartonMat = new THREE.MeshStandardMaterial({
			color,
			roughness: 0.72,
			metalness: 0.04,
		});
		const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), cartonMat);
		mesh.position.set(x, y + h / 2, z);
		mesh.castShadow = true;
		mesh.receiveShadow = true;
		scene.add(mesh);

		const edges = new THREE.LineSegments(
			new THREE.EdgesGeometry(mesh.geometry),
			new THREE.LineBasicMaterial({ color: 0x0f1724, transparent: true, opacity: 0.35 })
		);
		edges.position.copy(mesh.position);
		scene.add(edges);

		const tape = new THREE.Mesh(
			new THREE.BoxGeometry(w * 0.96, 0.025, d * 0.18),
			new THREE.MeshStandardMaterial({ color: 0xc6924b, roughness: 0.8 })
		);
		tape.position.set(x, y + h + 0.015, z);
		scene.add(tape);

		return h;
	},

	async render($container, stacks, spec, options = {}) {
		await this.load();

		const rows = spec.rows || 3;
		const cols = spec.cols || 10;
		const containerH = (spec.height_cm || 239) / 100;
		const width = Math.max($container.innerWidth() || 640, 320);
		const height = 420;

		const scene = new THREE.Scene();
		scene.background = new THREE.Color(0x0f1724);
		scene.fog = new THREE.Fog(0x0f1724, 16, 48);

		const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 200);
		camera.position.set(cols * 0.45, containerH + 1.8, cols * 0.8 + 3.2);

		const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
		renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
		renderer.setSize(width, height);
		renderer.shadowMap.enabled = true;
		renderer.shadowMap.type = THREE.PCFSoftShadowMap;
		$container.empty().append(renderer.domElement);

		const placedCount = options.placedCount || 0;
		const hud = $(`
			<div class="sl-3d-hud">
				<strong>${options.containerLabel || "Container"}</strong> ·
				${placedCount} ${__("cartons stacked")} ·
				${__("Drag to rotate")} · ${__("Scroll to zoom")}
			</div>
		`);
		$container.append(hud);

		const controls = new THREE.OrbitControls(camera, renderer.domElement);
		controls.enableDamping = true;
		controls.dampingFactor = 0.06;
		controls.maxPolarAngle = Math.PI / 2.02;
		controls.minDistance = 4;
		controls.maxDistance = 30;
		controls.target.set(0, containerH / 2, 0);

		scene.add(new THREE.AmbientLight(0xb8c6e0, 0.55));
		const sun = new THREE.DirectionalLight(0xffffff, 0.95);
		sun.position.set(8, 14, 6);
		sun.castShadow = true;
		sun.shadow.mapSize.width = 2048;
		sun.shadow.mapSize.height = 2048;
		scene.add(sun);
		const fill = new THREE.DirectionalLight(0x6ea8fe, 0.35);
		fill.position.set(-6, 4, -8);
		scene.add(fill);

		const slotW = 0.52;
		const slotD = 0.52;
		const contW = cols * slotW;
		const contD = rows * slotD;
		const scale = 0.0095;

		const floor = new THREE.Mesh(
			new THREE.PlaneGeometry(contW + 1.6, contD + 1.6),
			new THREE.MeshStandardMaterial({ color: 0x2b3442, roughness: 0.95 })
		);
		floor.rotation.x = -Math.PI / 2;
		floor.receiveShadow = true;
		scene.add(floor);

		const grid = new THREE.GridHelper(Math.max(contW, contD) + 1.2, 20, 0x3d4f68, 0x243044);
		grid.position.y = 0.01;
		scene.add(grid);

		const shellGeo = new THREE.BoxGeometry(contW + 0.12, containerH, contD + 0.12);
		const shell = new THREE.Mesh(
			shellGeo,
			new THREE.MeshPhysicalMaterial({
				color: 0x6c757d,
				transparent: true,
				opacity: 0.12,
				roughness: 0.55,
				metalness: 0.35,
				side: THREE.DoubleSide,
			})
		);
		shell.position.y = containerH / 2;
		scene.add(shell);

		const edgeLines = new THREE.LineSegments(
			new THREE.EdgesGeometry(shellGeo),
			new THREE.LineBasicMaterial({ color: 0x90caf9, transparent: true, opacity: 0.85 })
		);
		edgeLines.position.copy(shell.position);
		scene.add(edgeLines);

		const ghostMat = new THREE.MeshStandardMaterial({
			color: 0xdee2e6,
			transparent: true,
			opacity: 0.06,
			roughness: 1,
		});

		for (let r = 1; r <= rows; r++) {
			for (let c = 1; c <= cols; c++) {
				const key = `${r}-${c}`;
				const x = (c - (cols + 1) / 2) * slotW;
				const z = (r - (rows + 1) / 2) * slotD;
				const stack = stacks[key] || [];

				if (!stack.length) {
					const ghost = new THREE.Mesh(new THREE.BoxGeometry(slotW * 0.88, 0.04, slotD * 0.88), ghostMat);
					ghost.position.set(x, 0.02, z);
					scene.add(ghost);
					continue;
				}

				let y = 0.03;
				stack.forEach((carton) => {
					const dims = this.parse_dims_cm(carton.carton_dimension);
					const color = this.item_color(carton.so_item);
					const h = this.add_carton_mesh(scene, x, y, z, dims, color, scale);
					y += h + 0.01;
				});
			}
		}

		const viewer = {
			renderer,
			scene,
			camera,
			controls,
			animationId: null,
			resizeHandler: null,
		};

		const animate = () => {
			viewer.animationId = requestAnimationFrame(animate);
			controls.update();
			renderer.render(scene, camera);
		};

		const onResize = () => {
			const w = Math.max($container.innerWidth() || width, 320);
			camera.aspect = w / height;
			camera.updateProjectionMatrix();
			renderer.setSize(w, height);
		};
		viewer.resizeHandler = onResize;
		window.addEventListener("resize", onResize);

		animate();
		return viewer;
	},
};
