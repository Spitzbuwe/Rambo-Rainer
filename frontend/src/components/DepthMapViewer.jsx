import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { createDepthMeshGeometry } from '../utils/depthMeshGenerator.js';
import './DepthMapViewer.css';

const ADMIN_TOKEN = import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

const DepthMapViewer = ({ depthMapPath, depthMapDownloadUrl, imagePreview }) => {
  const containerRef = useRef(null);
  const sceneRef     = useRef(null);
  const cameraRef    = useRef(null);
  const rendererRef  = useRef(null);
  const meshRef      = useRef(null);
  const objectUrlRef = useRef(null);
  const animFrameRef = useRef(null);
  const controlsRef  = useRef({
    isRotating: false,
    previousMousePosition: { x: 0, y: 0 },
    rotation: { x: 0, y: 0 },
    zoom: 1,
  });

  const [isWireframe, setIsWireframe] = useState(false);
  const [isLoading,   setIsLoading]   = useState(true);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    if (!containerRef.current || !depthMapPath) return;

    let cancelled = false;

    // ── Three.js scene / camera / renderer ──────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);
    sceneRef.current = scene;

    const width  = containerRef.current.clientWidth  || 400;
    const height = containerRef.current.clientHeight || 300;
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.z = 3;
    cameraRef.current = camera;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
      renderer.setSize(width, height);
      renderer.setPixelRatio(window.devicePixelRatio);
      containerRef.current.appendChild(renderer.domElement);
      rendererRef.current = renderer;
    } catch (err) {
      setError('WebGL wird nicht unterstützt');
      setIsLoading(false);
      return;
    }

    // ── Animation loop (starts immediately, renders empty scene until mesh loads) ──
    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    // ── Mouse / wheel controls ───────────────────────────────────────────────
    const onMouseDown = (e) => {
      controlsRef.current.isRotating = true;
      controlsRef.current.previousMousePosition = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e) => {
      if (!controlsRef.current.isRotating || !meshRef.current) return;
      const dx = e.clientX - controlsRef.current.previousMousePosition.x;
      const dy = e.clientY - controlsRef.current.previousMousePosition.y;
      controlsRef.current.rotation.y += dx * 0.01;
      controlsRef.current.rotation.x += dy * 0.01;
      meshRef.current.rotation.order = 'YXZ';
      meshRef.current.rotation.y = controlsRef.current.rotation.y;
      meshRef.current.rotation.x = controlsRef.current.rotation.x;
      controlsRef.current.previousMousePosition = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => { controlsRef.current.isRotating = false; };

    const onWheel = (e) => {
      e.preventDefault();
      controlsRef.current.zoom += e.deltaY > 0 ? -0.1 : 0.1;
      controlsRef.current.zoom = Math.max(0.5, Math.min(10, controlsRef.current.zoom));
      cameraRef.current.position.z = 3 / controlsRef.current.zoom;
    };

    const onKeyDown = (e) => {
      if (e.shiftKey && e.key.toLowerCase() === 'w') setIsWireframe((p) => !p);
      if (e.key.toLowerCase() === 'r') resetView();
    };

    renderer.domElement.addEventListener('mousedown', onMouseDown);
    renderer.domElement.addEventListener('mousemove', onMouseMove);
    renderer.domElement.addEventListener('mouseup',   onMouseUp);
    renderer.domElement.addEventListener('wheel',     onWheel, { passive: false });
    window.addEventListener('keydown', onKeyDown);

    // ── Auth-fetch → blob URL → depth mesh ──────────────────────────────────
    (async () => {
      try {
        setIsLoading(true);

        const res = await fetch(depthMapPath, {
          headers: { 'X-Rambo-Admin': ADMIN_TOKEN },
        });
        if (!res.ok) throw new Error(`Depth-Map Download fehlgeschlagen: ${res.status}`);
        if (cancelled) return;

        const blob   = await res.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        objectUrlRef.current = blobUrl;

        // Build geometry from the blob URL (no auth needed for blob:)
        const geometry = await createDepthMeshGeometry(blobUrl, 64, 0.5);
        if (cancelled) return;

        const material = new THREE.MeshPhongMaterial({
          color:     0x4488ff,
          wireframe: false,
          specular:  0x111111,
          shininess: 200,
        });

        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);
        meshRef.current = mesh;

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(5, 10, 7);
        scene.add(dirLight);

        setIsLoading(false);
      } catch (err) {
        if (!cancelled) {
          console.error('[DepthMapViewer] Mesh creation error:', err);
          setError('Mesh-Erstellung fehlgeschlagen: ' + err.message);
          setIsLoading(false);
        }
      }
    })();

    // ── Cleanup ──────────────────────────────────────────────────────────────
    return () => {
      cancelled = true;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

      renderer.domElement.removeEventListener('mousedown', onMouseDown);
      renderer.domElement.removeEventListener('mousemove', onMouseMove);
      renderer.domElement.removeEventListener('mouseup',   onMouseUp);
      renderer.domElement.removeEventListener('wheel',     onWheel);
      window.removeEventListener('keydown', onKeyDown);

      renderer.dispose();

      if (objectUrlRef.current) {
        window.URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      if (containerRef.current && renderer.domElement.parentNode === containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, [depthMapPath]);

  // ── Wireframe toggle ───────────────────────────────────────────────────────
  useEffect(() => {
    if (meshRef.current?.material) {
      meshRef.current.material.wireframe = isWireframe;
    }
  }, [isWireframe]);

  const resetView = () => {
    controlsRef.current.rotation = { x: 0, y: 0 };
    controlsRef.current.zoom = 1;
    if (meshRef.current) {
      meshRef.current.rotation.x = 0;
      meshRef.current.rotation.y = 0;
    }
    if (cameraRef.current) cameraRef.current.position.z = 3;
  };

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch(depthMapDownloadUrl, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          'X-Rambo-Admin': ADMIN_TOKEN,
        },
      });

      if (!response.ok) throw new Error(`Download fehlgeschlagen: ${response.status}`);

      const blob = await response.blob();
      const url  = window.URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = (depthMapDownloadUrl || 'depth_map.png').split('/').pop();
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Download error:', err);
      alert('Download fehlgeschlagen');
    }
  };

  return (
    <div className="depth-map-viewer-container">
      {imagePreview && (
        <div className="depth-map-preview">
          <img src={imagePreview} alt="Depth Map Preview" />
        </div>
      )}

      <div className="viewer-wrapper">
        {isLoading && (
          <div className="viewer-loader">
            <div className="spinner" />
            <p>3D-Viewer wird geladen...</p>
          </div>
        )}

        {error && (
          <div className="viewer-error">
            <p>⚠️ {error}</p>
          </div>
        )}

        <div ref={containerRef} className="depth-map-viewer" />

        <div className="viewer-controls">
          <button
            className="control-btn wireframe-btn"
            onClick={() => setIsWireframe(!isWireframe)}
            title="Shift+W"
          >
            {isWireframe ? '🔲 Solid' : '⚙️ Wireframe'}
          </button>
          <button className="control-btn reset-btn" onClick={resetView} title="R">
            ↺ Reset
          </button>
          <button className="control-btn download-btn" onClick={handleDownload}>
            ⬇️ Download
          </button>
        </div>

        <div className="viewer-help">
          <p>
            <strong>Drag:</strong> Rotation |{' '}
            <strong>Scroll:</strong> Zoom |{' '}
            <strong>Shift+W:</strong> Wireframe |{' '}
            <strong>R:</strong> Reset
          </p>
        </div>
      </div>
    </div>
  );
};

export default DepthMapViewer;
