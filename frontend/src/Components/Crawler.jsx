import React from "react";
import axios from "axios";

import ApiResponseAlert from "./ApiResponseAlert";

import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";

const API_CRAWL_URL = "http://172.30.1.27:8006/crawl";

const Crawler = ({ fetchArtists }) => {
  const [startId, setStartId] = React.useState(null);
  const [numCrawls, setNumCrawls] = React.useState(5);
  const [alerts, setAlerts] = React.useState([]);
  const handleCrawl = (event) => {
    event.preventDefault();

    axios
      .post(API_CRAWL_URL, null, {
        params: {
          start_id: startId,
          num_crawls: numCrawls,
        },
      })
      .then(function (response) {
        const new_alert = (
          <ApiResponseAlert variant="primary" message="Crawl ok" />
        );
        setAlerts([...alerts, new_alert]);
        fetchArtists();
      })
      .catch(function (error) {
        const details = error.response.data.detail;

        details.forEach((detail) => {
          const new_alert = (
            <ApiResponseAlert variant="danger" message={detail.msg} />
          );

          setAlerts([...alerts, new_alert]);
        });
      });
  };

  return (
    <>
      {alerts}
      <Form>
        <Form.Group className="mb-3">
          <Form.Label>Starting Artist ID:</Form.Label>
          <Form.Control
            type="number"
            min="0"
            max="20000"
            onChange={(e) => setStartId(e.target.value)}
          />
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label>Number of Artists:</Form.Label>
          <Form.Select onChange={(e) => setNumCrawls(e.target.value)}>
            <option>1</option>
            <option selected>5</option>
            <option>10</option>
            <option>25</option>
            <option>50</option>
          </Form.Select>
        </Form.Group>
        <Button
          variant="primary"
          type="submit"
          className="float-right"
          onClick={handleCrawl}
        >
          Crawl
        </Button>
      </Form>
    </>
  );
};

export default Crawler;
