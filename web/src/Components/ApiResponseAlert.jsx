import React from "react";
import Alert from "react-bootstrap/Alert";

const ApiResponseAlert = ({ variant, message }) => {
  const [show, setShow] = React.useState(true);
  if (show) {
    return (
      <>
        <Alert variant={variant} onClose={() => setShow(false)} dismissible>
          {message}
        </Alert>
      </>
    );
  }
  return <></>;
};

export default ApiResponseAlert;
