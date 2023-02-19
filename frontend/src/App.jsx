import { React } from "react";
import { Routes, Route } from "react-router-dom";
import "bootstrap/dist/css/bootstrap.min.css";

import Container from "react-bootstrap/Container";

import Home from "./Components/Home";
import Navigation from "./Components/Navigation";
import Torrents from "./Components/Torrents";

function App() {
  return (
    <Container className="bg-light">
      <Navigation />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/torrents" element={<Torrents />} />
      </Routes>
    </Container>
  );
}

export default App;
