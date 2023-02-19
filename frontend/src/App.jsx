import { React, useEffect, useState } from "react";
import axios from "axios";
import "bootstrap/dist/css/bootstrap.min.css";

import Container from "react-bootstrap/Container";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

import Artists from "./Components/Artists";
import Crawler from "./Components/Crawler";

const API_ENDPOINT = "http://172.30.1.27:8006/artists";

function App() {
  const [artists, setArtists] = useState([]);
  const fetchArtists = () => {
    axios.get(API_ENDPOINT).then((response) => {
      setArtists(response.data);
    });
  };

  useEffect(() => {
    fetchArtists();
  }, []);

  return (
    <Container className="bg-light">
      <main>
        <div className="py-5 text-center">
          <h1>Deezer2Red</h1>
        </div>
        <Row>
          <Col className="mx-auto" lg="4">
            <Crawler fetchArtists={fetchArtists} />
          </Col>
        </Row>

        <Row>
          <Col>
            <Artists artists={artists} />
          </Col>
        </Row>
      </main>
    </Container>
  );
}

export default App;
