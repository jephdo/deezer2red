import React from "react";
import axios from "axios";

import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import InputGroup from "react-bootstrap/InputGroup";

const API_BASE_URL = "http://172.30.1.27:8006/";

const ReviewToolbar = ({ artist, setShowArtist }) => {
  const handleSearch = (event) => {
    event.preventDefault();
  };

  const handleReview = (event) => {
    event.preventDefault();

    axios
      .put(`${API_BASE_URL}artist/${artist.id}/review`)
      .then(function (response) {
        setShowArtist(false);
      });
  };

  return (
    <div>
      <Form className="card p-2">
        <InputGroup>
          <Form.Control
            type="text"
            value={artist.name}
            aria-label="Input group example"
            aria-describedby="btnGroupAddon"
          />
          <Button variant="secondary" type="submit" onClick={handleSearch}>
            Search
          </Button>
          <Button variant="danger" type="submit" onClick={handleReview}>
            Reviewed
          </Button>
        </InputGroup>
      </Form>
    </div>
  );
};

export default ReviewToolbar;
