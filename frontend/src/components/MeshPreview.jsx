import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import "./MeshPreview.css";

const ADMIN_TOKEN = import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

export default function MeshPreview({
  meshUrl,
  meshFilename,
  meshFormat,
  meshVertices,
  meshFaces,
  stlUrl,
  stlFilename,
  glbUrl,
  glbFilename,
}) {
  const containerRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const frameRef = useRef(null);
  const objectRef = useRef(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const handleDownload = async (url, filenameFallback) => {
    if (!url) return;
    try {
      const token = localStorage.getItem("authToken");
      const res = await fetch(url, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          "X-Rambo-Admin": ADMIN_TOKEN,
        },
      });
      if (!res.ok) {
        throw new Error(`Download fehlgeschlagen (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = filenameFallback || "mesh.obj";
      a.click();
      URL.revokeObjectURL(objUrl);
    } catch (err) {
      console.error("[MeshPreview] download error:", err);
      setError(err?.message || "Mesh-Download fehlgeschlagen");
    }
  };

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const previewUrl = String(glbUrl || meshUrl || "").trim();
    const previewKind = glbUrl ? "glb" : "obj";
    if (!previewUrl) {
      setError("Keine Mesh-URL vorhanden.");
      setLoading(false);
      return undefined;
    }

    let mounted = true;
    const container = containerRef.current;
    const width = Math.max(container.clientWidth, 300);
    const height = Math.max(container.clientHeight, 240);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111827);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(1.8, 1.2, 2.2);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0.25, 0);
    controlsRef.current = controls;

    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const dir = new THREE.DirectionalLight(0xffffff, 0.95);
    dir.position.set(2, 3, 4);
    scene.add(dir);

    const grid = new THREE.GridHelper(2.8, 20, 0x374151, 0x1f2937);
    grid.position.y = -0.02;
    scene.add(grid);

    const animate = () => {
      if (!mounted) return;
      frameRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const loadMesh = async () => {
      try {
        setLoading(true);
        setError("");
        const token = localStorage.getItem("authToken");
        const res = await fetch(previewUrl, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            "X-Rambo-Admin": ADMIN_TOKEN,
          },
        });
        if (!res.ok) {
          throw new Error(`Mesh-Datei nicht ladbar (HTTP ${res.status})`);
        }
        let root;
        if (previewKind === "glb") {
          const blob = await res.blob();
          const objectUrl = URL.createObjectURL(blob);
          try {
            const loader = new GLTFLoader();
            const gltf = await loader.loadAsync(objectUrl);
            root = gltf?.scene;
          } finally {
            URL.revokeObjectURL(objectUrl);
          }
        } else {
          const rawObj = await res.text();
          if (!rawObj || !rawObj.trim()) {
            throw new Error("Leere OBJ-Datei empfangen");
          }
          const loader = new OBJLoader();
          root = loader.parse(rawObj);
        }
        if (!root || !root.children?.length) {
          throw new Error(previewKind === "glb" ? "Ungültiges GLB-Format" : "Ungültiges OBJ-Format");
        }

        root.traverse((child) => {
          if (child.isMesh) {
            child.material = new THREE.MeshStandardMaterial({
              color: 0x60a5fa,
              roughness: 0.7,
              metalness: 0.1,
            });
            child.castShadow = false;
            child.receiveShadow = true;
            if (!child.geometry.attributes.normal) {
              child.geometry.computeVertexNormals();
            }
          }
        });

        const box = new THREE.Box3().setFromObject(root);
        const center = box.getCenter(new THREE.Vector3());
        root.position.sub(center);
        const size = box.getSize(new THREE.Vector3());
        const maxAxis = Math.max(size.x, size.y, size.z, 1e-6);
        const scale = 1.5 / maxAxis;
        root.scale.setScalar(scale);

        scene.add(root);
        objectRef.current = root;
        setLoading(false);
      } catch (err) {
        console.error("[MeshPreview] load error:", err);
        if (mounted) {
          setError(err?.message || "Mesh-Preview konnte nicht geladen werden");
          setLoading(false);
        }
      }
    };

    loadMesh();

    const onResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
      const w = Math.max(containerRef.current.clientWidth, 300);
      const h = Math.max(containerRef.current.clientHeight, 240);
      rendererRef.current.setSize(w, h);
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    return () => {
      mounted = false;
      window.removeEventListener("resize", onResize);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      controls.dispose();
      if (objectRef.current) {
        objectRef.current.traverse((child) => {
          if (child.isMesh) {
            child.geometry?.dispose?.();
            if (Array.isArray(child.material)) {
              child.material.forEach((mat) => mat?.dispose?.());
            } else {
              child.material?.dispose?.();
            }
          }
        });
        scene.remove(objectRef.current);
        objectRef.current = null;
      }
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [meshUrl, glbUrl]);

  return (
    <div className="mesh-preview-card">
      <div className="mesh-preview-header">
        <strong>🧩 Mesh-Preview (MVP)</strong>
        <span>{glbFilename || meshFilename || "mesh.obj"}</span>
      </div>
      <div className="mesh-preview-meta">
        <span>Format: {glbUrl ? "glb" : (meshFormat || "obj")}</span>
        <span>Vertices: {typeof meshVertices === "number" ? meshVertices : "n/a"}</span>
        <span>Faces: {typeof meshFaces === "number" ? meshFaces : "n/a"}</span>
      </div>
      <div className="mesh-preview-canvas-wrap">
        {loading ? <div className="mesh-preview-overlay">Mesh wird geladen...</div> : null}
        {error ? <div className="mesh-preview-overlay mesh-preview-error">⚠️ {error}</div> : null}
        <div ref={containerRef} className="mesh-preview-canvas" />
      </div>
      <div className="mesh-preview-actions">
        <button
          type="button"
          className="mesh-preview-download"
          onClick={() => handleDownload(meshUrl, meshFilename || "mesh.obj")}
          disabled={!meshUrl}
        >
          Download OBJ
        </button>
        {stlUrl ? (
          <button
            type="button"
            className="mesh-preview-download"
            onClick={() => handleDownload(stlUrl, stlFilename || "mesh.stl")}
          >
            Download STL
          </button>
        ) : null}
        {glbUrl ? (
          <button
            type="button"
            className="mesh-preview-download"
            onClick={() => handleDownload(glbUrl, glbFilename || "mesh.glb")}
          >
            Download GLB
          </button>
        ) : null}
      </div>
    </div>
  );
}
