import React from "react";
import axios from "axios";

import Badge from "react-bootstrap/Badge";
import Button from "react-bootstrap/Button";
import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Image from "react-bootstrap/Image";
import ListGroup from "react-bootstrap/ListGroup";

const API_BASE_URL = "http://172.30.1.27:8006/";

const Album = ({ album }) => {
  const pillBg = (() => {
    switch (album.record_type) {
      case "album":
        return "primary";
      case "ep":
        return "success";
      case "single":
        return "secondary";
      default:
        return "danger";
    }
  })();
  const isDisabled = album.record_type == "single";
  const deezerUrl = `https://www.deezer.com/album/${album.id}`;

  const [title, setTitle] = React.useState(album.title);

  const handleClick = (event) => {
    axios
      .post(`${API_BASE_URL}album/${album.id}/generate`)
      .then(function (response) {
        setTitle(<mark>{album.title}</mark>);
      })
      .catch(function (error) {
        setTitle(<s>{album.title}</s>);
      });
  };
  return (
    <ListGroup.Item>
      <div className="ms-2 me-auto">
        <Row>
          <Col lg="2">
            <a href={deezerUrl} target="_blank" rel="noopener noreferrer">
              <Image src={album.image_url} thumbnail />
            </a>
          </Col>
          <Col lg="8">
            {" "}
            <div className="fw-bold">
              {title}{" "}
              <Badge pill bg={pillBg}>
                {album.record_type}
              </Badge>{" "}
            </div>
            <div>
              <span>
                <kbd>{album.id}</kbd>
              </span>{" "}
              | <span>{album.release_date}</span>
            </div>
          </Col>
          <Col lg="2">
            {isDisabled ? (
              <Button variant="primary" disabled>
                Generate
              </Button>
            ) : (
              <Button variant="primary" onClick={handleClick}>
                Generate
              </Button>
            )}
          </Col>
        </Row>
      </div>
    </ListGroup.Item>
  );
};

export default Album;
