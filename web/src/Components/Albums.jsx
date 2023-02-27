import React from "react";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";

import Album from "./Album";
import Paginator from "./Paginator";

const Albums = ({ albums, fetchAlbums, pageSettings, availableActions }) => {
  return (
    <>
      {albums.map((album) => (
        <Row>
          <Col lg="8">
            <Album
              key={album.id}
              album={album}
              availableActions={availableActions}
            />
          </Col>
        </Row>
      ))}

      <Row className="d-flex justify-content-center">
        <Col className="col-lg-3">
          {" "}
          <Paginator
            page={pageSettings.page}
            pages={pageSettings.pages}
            pageSettings={pageSettings}
            fetchAlbums={fetchAlbums}
          />
          <div>
            Showing {albums.length} of {pageSettings.total}
          </div>
        </Col>
      </Row>
    </>
  );
};

export default Albums;
