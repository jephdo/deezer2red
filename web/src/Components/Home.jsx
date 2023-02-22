import { React, useEffect, useState } from "react";
import axios from "axios";

import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

import Artists from "./Artists";
import Crawler from "./Crawler";

const API_ENDPOINT = "http://172.30.1.27:8006/albums/tracked";

const Home = () => {
  const [artists, setArtists] = useState([]);
  const [pageSettings, setPageSettings] = useState({});
  const fetchArtists = (page = 1, size = 5) => {
    axios
      .get(API_ENDPOINT, { params: { page: page, size: size } })
      .then((response) => {
        setArtists(response.data.items);
        setPageSettings({
          page: response.data.page,
          pages: response.data.pages,
        });
        console.log(pageSettings);
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
          <Crawler fetchArtists={fetchArtists} pageSettings={pageSettings} />
        </Col>
      </Row>

      <Row>
        <Col>
          <Artists
            artists={artists}
            fetchArtists={fetchArtists}
            pageSettings={pageSettings}
            availableActions={availableActions}
            showToolbar={true}
          />
        </Col>
      </Row>
    </main>
  );
};

export default Home;
