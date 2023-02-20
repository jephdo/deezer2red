import { React } from "react";
import { Routes, Route } from "react-router-dom";
import "bootstrap/dist/css/bootstrap.min.css";

import Container from "react-bootstrap/Container";

import Home from "./Components/Home";
import Navigation from "./Components/Navigation";
import UploadManager from "./Components/UploadManager";

function App() {
  return (
    <Container className="bg-light">
      <Navigation />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/uploads" element={<UploadManager />} />
      </Routes>
    </Container>
  );
}

export default App;
