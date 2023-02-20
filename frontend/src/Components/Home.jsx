import { React, useEffect, useState } from "react";
import axios from "axios";

import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

import Artists from "./Artists";
import Crawler from "./Crawler";

const API_ENDPOINT = "http://172.30.1.27:8006/artists";

const Home = () => {
  const [artists, setArtists] = useState([]);
  const fetchArtists = () => {
    axios.get(API_ENDPOINT).then((response) => {
      setArtists(response.data);
    });
  };

  useEffect(() => {
    fetchArtists();
  }, []);

  const availableActions = {
    addAction: true,
  };
  return (
    <main>
      <Row>
        <Col className="mx-auto" lg="4">
          <Crawler fetchArtists={fetchArtists} />
        </Col>
      </Row>

      <Row>
        <Col>
          <Artists
            artists={artists}
            availableActions={availableActions}
            showToolbar={true}
          />
        </Col>
      </Row>
    </main>
  );
};

export default Home;
