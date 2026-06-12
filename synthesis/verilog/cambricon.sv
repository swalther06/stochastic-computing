// HA: half adder
module ha (
    input  a, b,
    output sum, cout
);
    assign sum  = a ^ b;
    assign cout = a & b;
endmodule