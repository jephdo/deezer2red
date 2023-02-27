import { React, useEffect, useState } from "react";
import axios from "axios";

import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

import Albums from "./Albums";

const API_ENDPOINT = "http://172.30.1.27:8006/albums/upload/ready";

const UploadManager = () => {
  const [albums, setAlbums] = useState([]);
  const [pageSettings, setPageSettings] = useState({});

  const fetchAlbums = (page = 1, size = 10) => {
    axios
      .get(API_ENDPOINT, { params: { page: page, size: size } })
      .then((response) => {
        setAlbums(response.data.items);
        setPageSettings({
          page: response.data.page,
          pages: response.data.pages,
          total: response.data.total,
          size: response.data.size,
        });
        console.log(pageSettings);
      });
  };

  useEffect(() => {
    fetchAlbums();
  }, []);

  const availableActions = {
    uploadAction: true,
    downloadAction: true,
    removeAction: true,
  };
  return (
    <>
      <main>
        <Row>
          <Col>
            <Albums
              albums={albums}
              fetchAlbums={fetchAlbums}
              pageSettings={pageSettings}
              availableActions={availableActions}
            />
          </Col>
        </Row>
      </main>
    </>
  );
};

export default UploadManager;
