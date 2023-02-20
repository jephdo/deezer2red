import { React, useEffect, useState } from "react";
import axios from "axios";

import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

import Artists from "./Artists";

const API_ENDPOINT = "http://172.30.1.27:8006/artists";

const UploadManager = () => {
  const [artists, setArtists] = useState([]);
  const fetchArtists = () => {
    axios
      .get(API_ENDPOINT, { params: { only_added: true } })
      .then((response) => {
        setArtists(response.data);
      });
  };

  useEffect(() => {
    fetchArtists();
  }, []);

  const availableActions = {
    uploadAction: true,
    downloadAction: true,
  };
  return (
    <>
      <main>
        <Row>
          <Col>
            <Artists
              artists={artists}
              availableActions={availableActions}
              showToolbar={false}
            />
          </Col>
        </Row>
      </main>
    </>
  );
};

export default UploadManager;
