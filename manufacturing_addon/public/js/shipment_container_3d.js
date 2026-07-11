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
		if (viewer.cleanup) viewer.cleanup();
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

	short_label(text, max = 28) {
		const value = text || "";
		return value.length > max ? `${value.slice(0, max)}…` : value;
	},

	add_carton_mesh(scene, cartonMeshes, x, y, z, dims, color, scale, carton) {
		let w = dims[0] * scale;
		let h = dims[2] * scale;
		let d = dims[1] * scale;
		w = Math.max(0.12, Math.min(w, 0.48));
		d = Math.max(0.12, Math.min(d, 0.48));
		h = Math.max(0.12, Math.min(h, 0.55));

		const cartonMat = new THREE.MeshStandardMaterial({
			color: color.clone(),
			roughness: 0.72,
			metalness: 0.04,
			emissive: new THREE.Color(0x000000),
		});
		const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), cartonMat);
		mesh.position.set(x, y + h / 2, z);
		mesh.castShadow = true;
		mesh.receiveShadow = true;
		mesh.userData = {
			type: "carton",
			carton,
			baseColor: color.clone(),
		};
		scene.add(mesh);
		cartonMeshes.push(mesh);

		const edges = new THREE.LineSegments(
			new THREE.EdgesGeometry(mesh.geometry),
			new THREE.LineBasicMaterial({ color: 0x0f1724, transparent: true, opacity: 0.35 })
		);
		edges.position.copy(mesh.position);
		edges.userData = { type: "decoration", parentCarton: mesh };
		scene.add(edges);
		mesh.userData.edge = edges;

		const tape = new THREE.Mesh(
			new THREE.BoxGeometry(w * 0.96, 0.025, d * 0.18),
			new THREE.MeshStandardMaterial({ color: 0xc6924b, roughness: 0.8 })
		);
		tape.position.set(x, y + h + 0.015, z);
		tape.userData = { type: "decoration", parentCarton: mesh };
		scene.add(tape);

		return h;
	},

	set_highlight(mesh, active) {
		if (!mesh || mesh.userData.type !== "carton") return;
		if (active) {
			mesh.material.emissive.setHex(0x4488ff);
			mesh.material.emissiveIntensity = 0.45;
			mesh.scale.set(1.05, 1.05, 1.05);
		} else {
			mesh.material.emissive.setHex(0x000000);
			mesh.material.emissiveIntensity = 0;
			mesh.scale.set(1, 1, 1);
		}
	},

	format_carton_info(carton) {
		if (!carton) return "";
		const layer = carton.position_layer || 1;
		const row = carton.position_row || "-";
		const col = carton.position_col || "-";
		return `
			<div><strong>${frappe.utils.escape_html(carton.carton_label || carton.name || "")}</strong></div>
			<div>${__("Position")}: R${row} C${col} L${layer}</div>
			<div>${__("Item")}: ${frappe.utils.escape_html(this.short_label(carton.so_item, 42))}</div>
			<div>${__("Size")}: ${frappe.utils.escape_html(carton.finished_size || "-")}</div>
			<div>${__("Pieces")}: ${format_number(flt(carton.qty_in_carton || 0), null, 0)} · ${__("Cartons in batch")}: ${carton.carton_count || 1}</div>
			<div>${__("Dimension")}: ${frappe.utils.escape_html(carton.carton_dimension || "-")}</div>
			<div>${__("Packing Report")}: ${frappe.utils.escape_html(carton.packing_report || "-")}</div>
		`;
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
		scene.fog = new THREE.Fog(0x0f1724, 20, 55);

		const camera = new THREE.PerspectiveCamera(50, width / height, 0.05, 200);
		camera.position.set(cols * 0.35, containerH * 0.9, cols * 0.65 + 2.5);

		const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
		renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
		renderer.setSize(width, height);
		renderer.shadowMap.enabled = true;
		renderer.shadowMap.type = THREE.PCFSoftShadowMap;
		$container.empty().append(renderer.domElement);

		const placedCount = options.placedCount || 0;
		const $hud = $(`
			<div class="sl-3d-hud">
				<div class="sl-3d-hud-top">
					<strong>${options.containerLabel || "Container"}</strong> · ${placedCount} ${__("cartons")} ·
					${__("Scroll on view to zoom")} · ${__("Hover/click cartons")}
				</div>
				<div class="sl-3d-hud-actions">
					<button type="button" class="btn btn-default btn-xs sl-3d-reset-view">${__("Reset View")}</button>
					<button type="button" class="btn btn-default btn-xs sl-3d-walk-in">${__("Walk Inside")}</button>
				</div>
			</div>
		`);
		const $tooltip = $(`<div class="sl-3d-tooltip" style="display:none;"></div>`);
		const $info = $(`<div class="sl-3d-info" style="display:none;"></div>`);
		$container.append($hud, $tooltip, $info);

		const controls = new THREE.OrbitControls(camera, renderer.domElement);
		controls.enableDamping = true;
		controls.dampingFactor = 0.08;
		controls.enablePan = true;
		controls.screenSpacePanning = true;
		controls.maxPolarAngle = Math.PI / 1.95;
		controls.minDistance = 0.6;
		controls.maxDistance = 35;
		controls.target.set(0, containerH * 0.45, 0);

		const defaultCamera = {
			position: camera.position.clone(),
			target: controls.target.clone(),
		};

		scene.add(new THREE.AmbientLight(0xb8c6e0, 0.55));
		const sun = new THREE.DirectionalLight(0xffffff, 0.95);
		sun.position.set(8, 14, 6);
		sun.castShadow = true;
		scene.add(sun);
		const fill = new THREE.DirectionalLight(0x6ea8fe, 0.35);
		fill.position.set(-6, 4, -8);
		scene.add(fill);

		const slotW = 0.52;
		const slotD = 0.52;
		const contW = cols * slotW;
		const contD = rows * slotD;
		const scale = 0.0095;
		const cartonMeshes = [];

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
				opacity: 0.1,
				roughness: 0.55,
				metalness: 0.35,
				side: THREE.DoubleSide,
				depthWrite: false,
			})
		);
		shell.position.y = containerH / 2;
		shell.userData = { type: "shell" };
		scene.add(shell);

		const edgeLines = new THREE.LineSegments(
			new THREE.EdgesGeometry(shellGeo),
			new THREE.LineBasicMaterial({ color: 0x90caf9, transparent: true, opacity: 0.75 })
		);
		edgeLines.position.copy(shell.position);
		scene.add(edgeLines);

		for (let r = 1; r <= rows; r++) {
			for (let c = 1; c <= cols; c++) {
				const key = `${r}-${c}`;
				const x = (c - (cols + 1) / 2) * slotW;
				const z = (r - (rows + 1) / 2) * slotD;
				const stack = stacks[key] || [];

				if (!stack.length) continue;

				let y = 0.03;
				stack.forEach((carton) => {
					const dims = this.parse_dims_cm(carton.carton_dimension);
					const color = this.item_color(carton.so_item);
					const h = this.add_carton_mesh(scene, cartonMeshes, x, y, z, dims, color, scale, carton);
					y += h + 0.01;
				});
			}
		}

		const raycaster = new THREE.Raycaster();
		const mouse = new THREE.Vector2();
		let hoveredMesh = null;
		let selectedMesh = null;

		const pickCartonMesh = (intersects) => {
			for (const hit of intersects) {
				let obj = hit.object;
				while (obj) {
					if (obj.userData && obj.userData.type === "carton") return obj;
					if (obj.userData && obj.userData.parentCarton) return obj.userData.parentCarton;
					obj = obj.parent;
				}
			}
			return null;
		};

		const focus_mesh = (mesh) => {
			if (!mesh) return;
			const pos = mesh.position.clone();
			controls.target.copy(pos);
			camera.position.lerp(new THREE.Vector3(pos.x + 1.2, pos.y + 0.8, pos.z + 1.6), 0.35);
		};

		const on_mouse_move = (event) => {
			const rect = renderer.domElement.getBoundingClientRect();
			mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
			mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
			raycaster.setFromCamera(mouse, camera);
			const mesh = pickCartonMesh(raycaster.intersectObjects(cartonMeshes, false));

			if (hoveredMesh && hoveredMesh !== mesh && hoveredMesh !== selectedMesh) {
				this.set_highlight(hoveredMesh, false);
			}
			hoveredMesh = mesh;

			if (mesh && mesh !== selectedMesh) {
				this.set_highlight(mesh, true);
				$tooltip
					.html(this.format_carton_info(mesh.userData.carton))
					.css({ left: event.clientX - rect.left + 12, top: event.clientY - rect.top + 12 })
					.show();
				renderer.domElement.style.cursor = "pointer";
			} else if (!selectedMesh) {
				$tooltip.hide();
				renderer.domElement.style.cursor = "grab";
			}
		};

		const on_click = (event) => {
			const rect = renderer.domElement.getBoundingClientRect();
			mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
			mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
			raycaster.setFromCamera(mouse, camera);
			const mesh = pickCartonMesh(raycaster.intersectObjects(cartonMeshes, false));

			if (selectedMesh && selectedMesh !== mesh) {
				this.set_highlight(selectedMesh, false);
			}

			if (!mesh) {
				selectedMesh = null;
				$info.hide();
				return;
			}

			selectedMesh = mesh;
			this.set_highlight(mesh, true);
			$info.html(`<div class="sl-3d-info-title">${__("Selected Carton")}</div>${this.format_carton_info(mesh.userData.carton)}`).show();
			focus_mesh(mesh);

			if (options.onSelect && mesh.userData.carton) {
				options.onSelect(mesh.userData.carton);
			}
		};

		const on_wheel = (event) => {
			event.preventDefault();
			event.stopPropagation();
		};

		const dom = renderer.domElement;
		dom.addEventListener("mousemove", on_mouse_move);
		dom.addEventListener("click", on_click);
		dom.addEventListener("wheel", on_wheel, { passive: false });

		$hud.find(".sl-3d-reset-view").on("click", () => {
			camera.position.copy(defaultCamera.position);
			controls.target.copy(defaultCamera.target);
			controls.update();
		});

		$hud.find(".sl-3d-walk-in").on("click", () => {
			camera.position.set(0, containerH * 0.55, 0.3);
			controls.target.set(0, containerH * 0.45, -1.5);
			controls.minDistance = 0.2;
			controls.update();
		});

		const viewer = {
			renderer,
			scene,
			camera,
			controls,
			animationId: null,
			resizeHandler: null,
			cleanup: () => {
				dom.removeEventListener("mousemove", on_mouse_move);
				dom.removeEventListener("click", on_click);
				dom.removeEventListener("wheel", on_wheel);
				$hud.find(".sl-3d-reset-view, .sl-3d-walk-in").off("click");
			},
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
